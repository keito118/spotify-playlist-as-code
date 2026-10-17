"""A tiny Spotify Web API client (standard library only).

Uses the playlist "items" endpoints introduced in the February 2026 Web API
changes (the older /tracks paths were removed).
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
BATCH = 100  # max URIs per playlist request

ENV_VARS = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN")


class SpotifyError(RuntimeError):
    pass


def have_credentials() -> bool:
    return all(os.environ.get(v) for v in ENV_VARS)


def _basic_auth(client_id: str, client_secret: str) -> str:
    return "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def exchange_token(client_id: str, client_secret: str, form: dict[str, str]) -> dict:
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(form).encode(),
        headers={
            "Authorization": _basic_auth(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SpotifyError(f"token request failed: {e.code} {e.read().decode(errors='replace')}") from e


class Client:
    def __init__(self, access_token: str):
        self.access_token = access_token

    @classmethod
    def from_env(cls) -> "Client":
        missing = [v for v in ENV_VARS if not os.environ.get(v)]
        if missing:
            raise SpotifyError("missing environment variables: " + ", ".join(missing))
        token = exchange_token(
            os.environ["SPOTIFY_CLIENT_ID"],
            os.environ["SPOTIFY_CLIENT_SECRET"],
            {"grant_type": "refresh_token", "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"]},
        )
        return cls(token["access_token"])

    def request(self, method: str, path: str, body: dict | None = None, retries: int = 3) -> dict | None:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            API + path,
            data=data,
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 429 and retries > 0:
                time.sleep(int(e.headers.get("Retry-After", "2")) + 1)
                return self.request(method, path, body, retries - 1)
            if e.code >= 500 and retries > 0:
                time.sleep(2)
                return self.request(method, path, body, retries - 1)
            raise SpotifyError(f"{method} {path} -> {e.code} {e.read().decode(errors='replace')}") from e

    def get_track(self, track_id: str) -> dict | None:
        """Return track metadata, or None if Spotify does not know the ID."""
        try:
            return self.request("GET", f"/tracks/{track_id}")
        except SpotifyError as e:
            if "-> 404" in str(e) or "-> 400" in str(e):
                return None
            raise

    def playlist_tracks(self, playlist_id: str) -> list[dict | None]:
        """The playlist's current tracks, in order (None for an unavailable entry)."""
        tracks: list[dict | None] = []
        offset = 0
        while True:
            page = self.request("GET", f"/playlists/{playlist_id}/items?limit=50&offset={offset}") or {}
            entries = page.get("items", [])
            for entry in entries:
                # The February 2026 API calls the field "item"; older responses used "track".
                tracks.append(entry.get("item") or entry.get("track"))
            offset += len(entries)
            if not page.get("next") or not entries:
                return tracks

    def replace_playlist(self, playlist_id: str, uris: list[str]) -> None:
        """Make the playlist contain exactly `uris`, in order."""
        first, rest = uris[:BATCH], uris[BATCH:]
        self.request("PUT", f"/playlists/{playlist_id}/items", {"uris": first})
        for i in range(0, len(rest), BATCH):
            self.request("POST", f"/playlists/{playlist_id}/items", {"uris": rest[i : i + BATCH]})
