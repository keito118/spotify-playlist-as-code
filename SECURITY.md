# Security

## Keeping your keys safe

- Store `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_REFRESH_TOKEN` only as GitHub Actions secrets. Never commit them or paste them into issues.
- Secrets are not copied to forks or to repositories made from the template, and pull requests from forks run without them.
- Anyone with write access to your copy can change a workflow and use its secrets, so give write access only to people you trust.
- If a token leaks, remove the app's access at <https://www.spotify.com/account/apps/>, reset the Client Secret in the Spotify Developer Dashboard, and register new secrets.

## Reporting a vulnerability

Please report security problems privately through **Security → Report a vulnerability** on this repository rather than in a public issue.
