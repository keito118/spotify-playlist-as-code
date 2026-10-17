# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-10-17

### Fixed

- The README CI badge showed no status because **Validate playlists** never ran on `main`. It now also runs on pushes to `main`.

## [0.1.0] - 2026-10-17

First public release.

### Added

- Playlist files in `playlists/`: one Spotify track per line, with `# @playlist` and `# @title` directives. Tracks can be URIs, `open.spotify.com` links or bare IDs.
- `python -m pac validate`: rejects malformed track IDs and duplicates, and with `--base` lists the songs added and removed. With Spotify secrets it also looks up each added track by name.
- `python -m pac sync`: makes each Spotify playlist match its file exactly, in batches of 100. Runs as a dry run when secrets are missing.
- GitHub Actions: **Validate playlists** on every pull request, **Sync to Spotify** on pushes to `main` and on manual runs.
- `scripts/get_refresh_token.py` to get a refresh token through Spotify's consent page on `http://127.0.0.1:8888/callback`.
- English and Japanese README and CONTRIBUTING, a pull request template, and setup troubleshooting.

### Notes

- Uses the playlist `/items` endpoints from Spotify's February 2026 Web API changes. Spotify's development mode requires the app owner to have Spotify Premium.
- Standard library only; Python 3.10 or later.

[Unreleased]: https://github.com/keito118/spotify-playlist-as-code/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/keito118/spotify-playlist-as-code/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/keito118/spotify-playlist-as-code/releases/tag/v0.1.0
