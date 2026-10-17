"""Work out who added each song, from the git history of the playlist file."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request

NOREPLY = re.compile(r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$", re.I)
CO_AUTHOR = re.compile(r"^Co-authored-by:\s*(.+?)\s*<([^>]+)>\s*$", re.I | re.M)
BOT = re.compile(r"\[bot\]$", re.I)


def blame(path: str) -> dict[int, str]:
    """Line number -> SHA of the commit that last changed that line ({} outside a git checkout)."""
    result = subprocess.run(["git", "blame", "--line-porcelain", "--", path], capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    lines: dict[int, str] = {}
    for row in result.stdout.splitlines():
        parts = row.split(" ")
        if len(parts) >= 3 and len(parts[0]) == 40 and all(c in "0123456789abcdef" for c in parts[0]):
            lines[int(parts[2])] = parts[0]
    return lines


def login_from_email(email: str) -> str | None:
    match = NOREPLY.match(email.strip())
    return match.group(1) if match else None


def _api_login(sha: str) -> str | None:
    """The GitHub account behind a commit, when running in Actions with a token."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        return None
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits/{sha}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return (json.load(resp).get("author") or {}).get("login")
    except Exception:
        return None


def person(sha: str) -> str | None:
    """Who to credit for a commit ("@login", or a plain name when the account is unknown).

    For a bot commit, that is the co-author it names (the "Add a song" workflow credits
    the person who opened the issue this way); otherwise it is the author.
    """
    show = subprocess.run(["git", "show", "-s", "--format=%an%x00%ae%x00%B", sha], capture_output=True, text=True)
    if show.returncode != 0:
        return None
    name, email, body = (show.stdout.split("\x00", 2) + ["", ""])[:3]
    if BOT.search(name) or BOT.search(login_from_email(email) or ""):
        for co_name, co_email in CO_AUTHOR.findall(body):
            if not BOT.search(co_name):
                login = login_from_email(co_email)
                return f"@{login}" if login else co_name
        return None
    login = login_from_email(email) or _api_login(sha)
    return f"@{login}" if login else (name or None)


def song_credits(pl) -> dict[str, str]:
    """Track ID -> who added it (see `person`), for the tracks in a playlist file."""
    by_line = blame(pl.path)
    cache: dict[str, str | None] = {}
    credits: dict[str, str] = {}
    for track in pl.tracks:
        sha = by_line.get(track.line)
        if not sha or set(sha) == {"0"}:  # uncommitted line
            continue
        if sha not in cache:
            cache[sha] = person(sha)
        if cache[sha]:
            credits[track.id] = cache[sha]
    return credits
