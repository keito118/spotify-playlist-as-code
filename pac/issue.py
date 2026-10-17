"""Read "Add a song" issue forms.

GitHub renders an issue form as Markdown, one "### Label" heading per field
with the answer below it ("_No response_" when an optional field is empty).
"""

from __future__ import annotations

import re

from .playlist import parse_track_ref

NO_RESPONSE = "_No response_"
TRACK_IN_TEXT_RE = re.compile(
    r"(spotify:track:[A-Za-z0-9]{22}"
    r"|https?://open\.spotify\.com/(?:intl-[a-z]{2}(?:-[A-Za-z]+)?/)?track/[A-Za-z0-9]{22}\S*)"
)


def parse_form(body: str) -> dict[str, str]:
    """Map each "### Heading" in an issue form body to its answer ("" if empty)."""
    fields: dict[str, str] = {}
    heading = None
    lines: list[str] = []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            if heading is not None:
                fields[heading] = _answer(lines)
            heading, lines = line[4:].strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        fields[heading] = _answer(lines)
    return fields


def _answer(lines: list[str]) -> str:
    text = "\n".join(lines).strip()
    return "" if text == NO_RESPONSE else text


def find_track(text: str) -> str | None:
    """The first Spotify track in free text, such as "Song by Artist https://open.spotify.com/track/…"."""
    stripped = text.strip()
    track_id = parse_track_ref(stripped)
    if track_id:
        return track_id
    m = TRACK_IN_TEXT_RE.search(text)
    return parse_track_ref(m.group(1)) if m else None
