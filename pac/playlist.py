"""Parse playlist files: one Spotify track per line, plus a few directives.

File format::

    # @playlist 3cEYpjA9oz9GiPac4AsH4n   <- Spotify playlist ID to sync to
    # @title Work BGM                   <- display name (optional)
    # Any other line starting with "#" is a comment.

    spotify:track:4uLU6hMCjMI75M1A2tKUQC          # Rick Astley - Never Gonna Give You Up
    https://open.spotify.com/track/11dFghVXANMlKmJXsNCbNl?si=abc  # Carly Rae Jepsen
    11dFghVXANMlKmJXsNCbNl

Each track line may be a URI, an open.spotify.com URL, or a bare 22-char ID,
optionally followed by "# note" (usually "Artist - Title").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
URI_RE = re.compile(r"^spotify:track:([A-Za-z0-9]+)$")
URL_RE = re.compile(
    r"^https?://open\.spotify\.com/(?:intl-[a-z]{2}(?:-[A-Za-z]+)?/)?track/([A-Za-z0-9]+)(?:[?/].*)?$"
)
DIRECTIVE_RE = re.compile(r"^#\s*@(\w+)\s+(.+?)\s*$")


@dataclass
class Track:
    id: str
    line: int
    note: str = ""

    @property
    def uri(self) -> str:
        return f"spotify:track:{self.id}"


@dataclass
class Problem:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


@dataclass
class Playlist:
    path: str
    spotify_id: str | None = None
    title: str | None = None
    tracks: list[Track] = field(default_factory=list)
    errors: list[Problem] = field(default_factory=list)
    warnings: list[Problem] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.title or Path(self.path).stem

    @property
    def uris(self) -> list[str]:
        return [t.uri for t in self.tracks]


def parse_track_ref(text: str) -> str | None:
    """Return the track ID in a URI, URL or bare ID, or None if unrecognised."""
    for pattern in (URI_RE, URL_RE):
        m = pattern.match(text)
        if m:
            text = m.group(1)
            break
    return text if ID_RE.match(text) else None


def parse(text: str, path: str = "<string>") -> Playlist:
    pl = Playlist(path=path)
    seen: dict[str, int] = {}

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#"):
            m = DIRECTIVE_RE.match(line)
            if not m:
                continue
            key, value = m.group(1).lower(), m.group(2)
            if key == "playlist":
                ref = value.split()[0]
                ref = re.sub(r"^spotify:playlist:", "", ref)
                ref = re.sub(r"^https?://open\.spotify\.com/playlist/", "", ref).split("?")[0]
                if ID_RE.match(ref):
                    pl.spotify_id = ref
                else:
                    pl.errors.append(Problem(path, lineno, f"invalid playlist ID: {value!r}"))
            elif key == "title":
                pl.title = value
            else:
                pl.warnings.append(Problem(path, lineno, f"unknown directive @{key}"))
            continue

        ref, _, note = line.partition("#")
        ref, note = ref.strip(), note.strip()
        track_id = parse_track_ref(ref)
        if track_id is None:
            pl.errors.append(Problem(path, lineno, f"not a Spotify track: {ref!r}"))
            continue
        if track_id in seen:
            pl.errors.append(
                Problem(path, lineno, f"duplicate track {track_id} (first on line {seen[track_id]})")
            )
            continue
        seen[track_id] = lineno
        pl.tracks.append(Track(id=track_id, line=lineno, note=note))

    if pl.spotify_id is None:
        pl.warnings.append(Problem(path, 1, "no '# @playlist <id>' line; this file will not be synced"))
    if len(pl.tracks) > 10_000:
        pl.errors.append(Problem(path, 1, "Spotify playlists hold at most 10,000 tracks"))
    return pl


def load(path: Path) -> Playlist:
    return parse(path.read_text(encoding="utf-8"), str(path))


def load_dir(directory: Path) -> list[Playlist]:
    return [load(p) for p in sorted(directory.glob("*.txt"))]
