"""Command line entry point.

    python -m pac validate [--base origin/main] [--check-online]
    python -m pac sync [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import __version__, spotify
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
