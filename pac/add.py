"""Append a track to a playlist file (used by the "Add a song" issue workflow)."""

from __future__ import annotations

from pathlib import Path

from .playlist import Playlist


class AddError(Exception):
    """A problem to report back to the person who suggested the song."""


def pick_playlist(playlists: list[Playlist], wanted: str) -> Playlist:
    """The playlist named by file name or @title, or the only one when `wanted` is empty."""
    if not playlists:
        raise AddError("This repository has no playlist files yet.")
    names = ", ".join(f"`{Path(p.path).stem}`" for p in playlists)
    if not wanted:
        if len(playlists) == 1:
            return playlists[0]
        raise AddError(f"Please say which playlist to add to. Choose one of: {names}.")
    key = wanted.strip().lower().removesuffix(".txt")
    for pl in playlists:
        if key in (Path(pl.path).stem.lower(), (pl.title or "").lower()):
            return pl
    raise AddError(f"There is no playlist called {wanted.strip()!r}. Choose one of: {names}.")


def track_label(info: dict) -> str:
    """ "Artist, Artist - Title" on one line, safe to put after "#" in a playlist file."""
    artists = ", ".join(a.get("name", "") for a in info.get("artists", []))
    label = f"{artists} - {info.get('name', '?')}" if artists else info.get("name", "?")
    return " ".join(label.split())


def append_track(pl: Playlist, track_id: str, note: str) -> str:
    """Add the track to the end of the playlist file and return the line written."""
    if pl.errors:
        raise AddError(f"`{pl.path}` has errors to fix first: {pl.errors[0].message}.")
    if any(t.id == track_id for t in pl.tracks):
        raise AddError(f"That song is already in {pl.name}.")
    line = f"https://open.spotify.com/track/{track_id}"
    if note:
        line += f"  # {note}"
    path = Path(pl.path)
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + line + "\n", encoding="utf-8")
    return line
