"""Get a Spotify refresh token for the sync workflow. Run once, on your own computer.

    python scripts/get_refresh_token.py

It asks for your app's Client ID and Client Secret, opens Spotify's consent
page in your browser, catches the redirect on http://127.0.0.1:8888/callback
and prints the refresh token. Paste the three values into the repository's
Actions secrets; never commit them.
"""

from __future__ import annotations

import http.server
import os
import re
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pac.spotify import exchange_token  # noqa: E402

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"


CREDENTIAL_RE = re.compile(r"^[0-9a-f]{32}$")


def ask(name: str, env_var: str) -> str:
    """Read a Client ID / Secret from the environment or the keyboard.

    Input is shown on screen on purpose: hidden prompts (getpass) do not
    accept Ctrl+V on Windows and silently store a control character instead.
    """
    value = os.environ.get(env_var, "").strip()
    while not CREDENTIAL_RE.match(value):
        if value:
            print(f"That doesn't look like a {name} (32 characters, 0-9 and a-f). Try again.")
        value = input(f"{name}: ").strip()
    return value


def main() -> None:
    client_id = ask("Client ID", "SPOTIFY_CLIENT_ID")
    client_secret = ask("Client Secret", "SPOTIFY_CLIENT_SECRET")
    state = secrets.token_urlsafe(16)
    result: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in query.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Done. You can close this tab and go back to the terminal.".encode())

        def log_message(self, *args):
            pass

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )
    print(f"\nOpening Spotify in your browser. If nothing happens, open this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    with http.server.HTTPServer(("127.0.0.1", 8888), Handler) as server:
        while "code" not in result and "error" not in result:
            server.handle_request()

    if result.get("state") != state:
        sys.exit("State mismatch; aborting.")
    if "error" in result:
        sys.exit(f"Spotify returned an error: {result['error']}")

    token = exchange_token(
        client_id,
        client_secret,
        {"grant_type": "authorization_code", "code": result["code"], "redirect_uri": REDIRECT_URI},
    )
    print("SPOTIFY_REFRESH_TOKEN:\n" + token["refresh_token"])


if __name__ == "__main__":
    main()
