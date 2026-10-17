"""Command line entry point.

    python -m pac validate [--base origin/main] [--check-online]
    python -m pac sync [--dry-run]
    python -m pac status [--image-dir DIR]
    python -m pac add <link> [--playlist NAME]
    python -m pac add --from-issue          # used by the "Add a song" workflow
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

from . import __version__, card, credits, spotify
from .add import AddError, append_track, pick_playlist, track_label
from .issue import find_track, parse_form
from .playlist import Playlist, Problem, load_dir, parse

PLAYLIST_DIR = Path("playlists")


def write_summary(markdown: str) -> None:
    """Print, and append to the GitHub Actions job summary when running in CI."""
    print(markdown)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def annotate(level: str, problem) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level} file={problem.path},line={problem.line}::{problem.message}")


def base_version(ref: str, path: str) -> Playlist | None:
    """The playlist file as it was at `ref`, or None if it did not exist."""
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return parse(result.stdout, path)


def diff(old: Playlist | None, new: Playlist) -> tuple[list, list]:
    old_ids = {t.id for t in old.tracks} if old else set()
    new_ids = {t.id for t in new.tracks}
    added = [t for t in new.tracks if t.id not in old_ids]
    removed = [t for t in old.tracks if t.id not in new_ids] if old else []
    return added, removed


def label(track, info: dict | None = None) -> str:
    if info:
        artists = ", ".join(a["name"] for a in info.get("artists", []))
        return f"{artists} - {info.get('name', '?')}"
    return track.note or track.id


def cmd_validate(args) -> int:
    playlists = load_dir(PLAYLIST_DIR)
    if not playlists:
        print(f"no playlist files found in {PLAYLIST_DIR}/", file=sys.stderr)
        return 1

    client = None
    if args.check_online:
        if spotify.have_credentials():
            client = spotify.Client.from_env()
        else:
            print("Spotify secrets not available; skipping the online check.")

    errors = 0
    lines = ["## 🎧 Playlist check", ""]
    for pl in playlists:
        for w in pl.warnings:
            annotate("warning", w)
        for e in pl.errors:
            annotate("error", e)
        errors += len(pl.errors)

        old = base_version(args.base, pl.path) if args.base else None
        added, removed = diff(old, pl) if args.base else ([], [])
        if args.base and old is not None and not added and not removed and not pl.errors:
            continue  # unchanged file, keep the summary short

        status = "❌" if pl.errors else "✅"
        lines.append(f"### {status} {pl.name} (`{pl.path}`, {len(pl.tracks)} tracks)")
        for e in pl.errors:
            lines.append(f"- ❌ line {e.line}: {e.message}")
        for w in pl.warnings:
            lines.append(f"- ⚠️ {w.message}")
        for t in added:
            info = None
            if client:
                info = client.get_track(t.id)
                if info is None:
                    errors += 1
                    msg = f"track {t.id} was not found on Spotify"
                    annotate("error", Problem(pl.path, t.line, msg))
                    lines.append(f"- ❌ line {t.line}: {msg}")
                    continue
            lines.append(f"- ➕ {label(t, info)}")
        for t in removed:
            lines.append(f"- ➖ {label(t)}")
        lines.append("")

    if len(lines) == 2:
        lines.append("No playlist changes.")
    write_summary("\n".join(lines))
    return 1 if errors else 0


def cmd_sync(args) -> int:
    playlists = load_dir(PLAYLIST_DIR)
    broken = [p for p in playlists if p.errors]
    if broken:
        for pl in broken:
            for e in pl.errors:
                print(e, file=sys.stderr)
        return 1

    dry_run = args.dry_run or not spotify.have_credentials()
    if dry_run and not args.dry_run:
        print("Spotify secrets are not set; running as a dry run.")
    client = None if dry_run else spotify.Client.from_env()

    lines = ["## 🔄 Spotify sync" + (" (dry run)" if dry_run else ""), ""]
    for pl in playlists:
        if not pl.spotify_id:
            lines.append(f"- ⏭️ {pl.name}: no `@playlist` ID, skipped")
            continue
        if client:
            client.replace_playlist(pl.spotify_id, pl.uris)
        url = f"https://open.spotify.com/playlist/{pl.spotify_id}"
        lines.append(f"- ✅ [{pl.name}]({url}): {len(pl.tracks)} tracks")
    write_summary("\n".join(lines))
    return 0


def status_lines(pl: Playlist, tracks: list[dict | None], added_by: dict[str, str] | None = None) -> list[str]:
    """Markdown for one playlist: what Spotify has now, and how it differs from the file."""
    url = f"https://open.spotify.com/playlist/{pl.spotify_id}"
    live_ids = [t.get("id") if t else None for t in tracks]
    file_ids = [t.id for t in pl.tracks]
    if live_ids == file_ids:
        state = "✅ matches the file"
    else:
        state = "⚠️ differs from the file (the next sync will fix it)"
    lines = [f"### [{pl.name}]({url}): {len(tracks)} tracks, {state}", ""]
    if tracks:
        added_by = added_by or {}
        lines += ["| # | Song | Artist | Added by |", "|---:|---|---|---|"]
        for i, t in enumerate(tracks, 1):
            if not t:
                lines.append(f"| {i} | _(unavailable)_ | | |")
                continue
            title = t.get("name", "?").replace("|", "\\|")
            artists = ", ".join(a["name"] for a in t.get("artists", [])).replace("|", "\\|")
            link = (t.get("external_urls") or {}).get("spotify")
            who = added_by.get(t.get("id", ""), "").replace("|", "\\|")
            lines.append(f"| {i} | {f'[{title}]({link})' if link else title} | {artists} | {who} |")
        lines.append("")
    missing = [t for t in pl.tracks if t.id not in set(live_ids)]
    extra = [t for t in tracks if t and t.get("id") not in set(file_ids)]
    for t in missing:
        lines.append(f"- ➖ In the file but not on Spotify: {label(t)}")
    for t in extra:
        lines.append(f"- ➕ On Spotify but not in the file: {label(None, t)}")
    if missing or extra:
        lines.append("")
    return lines


def cmd_status(args) -> int:
    playlists = load_dir(PLAYLIST_DIR)
    if not spotify.have_credentials():
        write_summary("## 🎧 Playlist status\n\nSpotify secrets are not set, so the live playlists can't be read.")
        return 0
    client = spotify.Client.from_env()
    lines = ["## 🎧 Playlist status", ""]
    for pl in playlists:
        if not pl.spotify_id:
            lines += [f"- ⏭️ {pl.name}: no `@playlist` ID, skipped", ""]
            continue
        tracks = client.playlist_tracks(pl.spotify_id)
        added_by = credits.song_credits(pl)
        lines += status_lines(pl, tracks, added_by)
        if args.image_dir:
            out = Path(args.image_dir) / f"{Path(pl.path).stem}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(card.render(pl.name, tracks, added_by), encoding="utf-8")
    write_summary("\n".join(lines))
    return 0


def set_output(name: str, value: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        delimiter = f"__PAC_{secrets.token_hex(8)}__"
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def add_track(ref: str, playlist_name: str) -> tuple[Playlist, str, str]:
    """Append the track to a playlist file; return the playlist, its label and the line written."""
    track_id = find_track(ref)
    if track_id is None:
        raise AddError(
            "That doesn't look like a Spotify song link. In Spotify, use Share → Copy Song Link "
            "and paste it (album and playlist links don't work)."
        )
    pl = pick_playlist(load_dir(PLAYLIST_DIR), playlist_name)
    label = ""
    if spotify.have_credentials():
        info = spotify.Client.from_env().get_track(track_id)
        if info is None:
            raise AddError(f"Spotify doesn't know the track `{track_id}`. Please check the link.")
        label = track_label(info)
    line = append_track(pl, track_id, label)
    return pl, label or track_id, line


def issue_pr_body(fields: dict[str, str], label: str) -> str:
    why = fields.get("Why this one?") or "_Not given._"
    where = fields.get("Listening from") or "_Not given._"
    author = os.environ.get("ISSUE_AUTHOR", "")
    number = os.environ.get("ISSUE_NUMBER", "")
    lines = [
        "## 🎵 Song(s)",
        "",
        label,
        "",
        "## Why this one?",
        "",
        why,
        "",
        "## Listening from (optional)",
        "",
        where,
    ]
    if number:
        lines += ["", f"Suggested by @{author} in #{number}. Closes #{number}."]
    return "\n".join(lines) + "\n"


def cmd_add(args) -> int:
    fields = parse_form(os.environ.get("ISSUE_BODY", "")) if args.from_issue else {}
    ref = fields.get("Song link", "") if args.from_issue else (args.link or "")
    playlist_name = args.playlist or fields.get("Playlist", "")
    try:
        pl, label, line = add_track(ref, playlist_name)
    except AddError as e:
        print(f"error: {e}", file=sys.stderr)
        if not args.from_issue:
            return 1
        set_output("ok", "false")
        set_output("error", str(e))
        return 0

    print(f"Added to {pl.path}: {line}")
    if args.from_issue:
        set_output("ok", "true")
        set_output("label", label)
        set_output("file", pl.path)
        body_file = os.environ.get("PR_BODY_FILE")
        if body_file:
            Path(body_file).write_text(issue_pr_body(fields, label), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pac", description="Playlist as Code")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="check playlist files and summarise changes")
    v.add_argument("--base", help="git ref to diff against, e.g. origin/main")
    v.add_argument("--check-online", action="store_true", help="look up added tracks on Spotify")
    v.set_defaults(func=cmd_validate)

    s = sub.add_parser("sync", help="push playlist files to Spotify")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_sync)

    st = sub.add_parser("status", help="show what is on Spotify right now")
    st.add_argument("--image-dir", help="also write <playlist>.svg track list images here")
    st.set_defaults(func=cmd_status)

    a = sub.add_parser("add", help="append a song to a playlist file")
    a.add_argument("link", nargs="?", help="Spotify song link, URI or ID")
    a.add_argument("--playlist", help="playlist file name or @title (needed when there are several)")
    a.add_argument("--from-issue", action="store_true", help="read the link from the ISSUE_BODY issue form")
    a.set_defaults(func=cmd_add)

    args = parser.parse_args(argv)
    if args.command == "add" and not (args.link or args.from_issue):
        parser.error("add needs a song link (or --from-issue)")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
