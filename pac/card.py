"""Render a playlist's current tracks as an SVG image for the README."""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from xml.sax.saxutils import escape

WIDTH = 640
ROW = 30
TOP = 84
BOTTOM = 44
TEXT_BUDGET = 70  # in half-width characters; wide (e.g. CJK) characters count as 2


def _width(ch: str) -> int:
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def fit(text: str, budget: int) -> str:
    """Cut `text` to about `budget` half-width columns, ending with … when shortened."""
    used = 0
    for i, ch in enumerate(text):
        used += _width(ch)
        if used > budget:
            return text[: max(i - 1, 0)] + "…"
    return text


def render(
    title: str,
    tracks: list[dict | None],
    credits: dict[str, str] | None = None,
    now: datetime | None = None,
) -> str:
    """`credits` maps track IDs to who added them, shown at the right of each row."""
    now = now or datetime.now(timezone.utc)
    credits = credits or {}
    height = TOP + ROW * max(len(tracks), 1) + BOTTOM
    count = f"{len(tracks)} track" + ("" if len(tracks) == 1 else "s")
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(title, {chr(34): "&quot;"})}">',
        "<style>",
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,"
        "'Hiragino Sans','Noto Sans CJK JP',sans-serif}",
        ".t{font-size:22px;font-weight:700;fill:#fff}.c{font-size:13px;fill:#b3b3b3}",
        ".n{font-size:14px;fill:#1db954;font-variant-numeric:tabular-nums}",
        ".s{font-size:15px;font-weight:600;fill:#fff}.a{font-size:15px;fill:#b3b3b3}",
        ".f{font-size:11px;fill:#6a6a6a}.w{font-size:12px;fill:#6a6a6a}",
        "</style>",
        f'<rect width="{WIDTH}" height="{height}" rx="14" fill="#121212"/>',
        f'<text x="24" y="42" class="t">{escape(fit(title, 44))}</text>',
        f'<text x="{WIDTH - 24}" y="42" class="c" text-anchor="end">{count}</text>',
        f'<line x1="24" y1="60" x2="{WIDTH - 24}" y2="60" stroke="#282828"/>',
    ]
    if not tracks:
        out.append(f'<text x="24" y="{TOP + 16}" class="a">No songs yet.</text>')
    for i, t in enumerate(tracks, 1):
        y = TOP + ROW * (i - 1) + 16
        out.append(f'<text x="44" y="{y}" class="n" text-anchor="end">{i}</text>')
        if not t:
            out.append(f'<text x="60" y="{y}" class="a">(unavailable)</text>')
            continue
        song = t.get("name", "?")
        artists = ", ".join(a["name"] for a in t.get("artists", []))
        who = fit(credits.get(t.get("id", ""), ""), 18)
        # The credit is drawn smaller, so it takes about 4/5 of a column per character.
        budget = TEXT_BUDGET - (sum(_width(ch) for ch in who) * 4 // 5 + 3 if who else 0)
        song = fit(song, budget * 3 // 5)
        used = sum(_width(ch) for ch in song)
        artists = fit(artists, max(budget - used - 3, 8))
        out.append(
            f'<text x="60" y="{y}"><tspan class="s">{escape(song)}</tspan>'
            f'<tspan class="a"> · {escape(artists)}</tspan></text>'
        )
        if who:
            out.append(f'<text x="{WIDTH - 24}" y="{y}" class="w" text-anchor="end">{escape(who)}</text>')
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    out.append(f'<text x="24" y="{height - 18}" class="f">Live from Spotify · updated {stamp}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
