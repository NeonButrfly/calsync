# CalSync

## Project Overview

CalSync is a self-hosted, read-only calendar aggregation service for Linux and Unix hosts. This Phase 1 foundation delivers a Dockerized FastAPI application with persistent storage, first-run admin setup, mandatory MFA with TOTP, mock provider sync, protected admin pages, background worker wiring, and read-only ICS publishing.

The application is designed for local and LAN-first operation:

- Default local URL: `http://localhost:3080`
- Default LAN URL: `http://SERVER-IP:3080`
- Default bind host: `APP_HOST=0.0.0.0`
- Default bind port: `APP_PORT=3080`
- Optional public URL override: `PUBLIC_BASE_URL`

## Current Phase 2 Scope

Implemented today:

- first-run admin setup with username or email, strong password, mandatory MFA, QR enrollment, and recovery codes
- password plus TOTP login for the admin UI
- local break-glass commands for `reset-admin-password` and `reset-admin-mfa`
- mock provider discovery and event import into the normalized event store
- Google provider settings in the admin UI for deployment-wide OAuth credentials
- Google account connection through browser-based OAuth with multiple account support
- Google calendar discovery with calendars disabled by default until explicitly enabled
- Google read-only event sync into the normalized event store
- Apple/iCloud CalDAV account onboarding with per-account app-specific passwords
- Apple/iCloud calendar discovery with calendars disabled by default until explicitly enabled
- combined read-only ICS feed publishing with stable tokens and token rotation
- protected admin dashboard, calendars management, sync status, and ICS publishing pages
- protected provider settings and connected-accounts pages for mock, Google, and Apple onboarding
- separate `web`, `worker`, and `db` services for Docker deployment

Not implemented yet:

- production hardening such as TLS termination, rate limiting, email delivery, and advanced worker retry policy

## Docker Deployment

1. Copy `.env.example` to `.env`.
2. Set real values for `SESSION_SECRET` and `ENCRYPTION_KEY`.
3. Review `APP_HOST=0.0.0.0`, `APP_PORT=3080`, and `PUBLIC_BASE_URL`.
4. Run `docker compose up --build`.
5. Open `http://localhost:3080` or `http://SERVER-IP:3080`.

The default `.env.example` includes:

- `APP_HOST=0.0.0.0`
- `APP_PORT=3080`
- `PUBLIC_BASE_URL=`
- `CALSYNC_DATABASE_URL=postgresql+psycopg://calsync:calsync@db:5432/calsync`
- `SYNC_POLL_SECONDS=300`
- optional `GOOGLE_OAUTH_CLIENT_ID`
- optional `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_SCOPES`
- `GOOGLE_OAUTH_REDIRECT_PATH`

Changing the published web port:

1. Edit `.env`
2. Change `APP_PORT=3080` to another port such as `APP_PORT=3180`
3. Restart with `docker compose up --build`

The Compose file publishes `${APP_PORT:-3080}:${APP_PORT:-3080}`, so the host port follows the value in `.env`.

## First-Run Admin Setup

On a brand-new database, CalSync exposes the first-run admin setup screen instead of a default login. No default username or password ships with the app.

The first-run admin setup flow requires:

- username or email
- strong password
- password confirmation
- MFA enrollment before the account is activated

The setup screen shows:

- a TOTP QR code for authenticator apps
- the plain TOTP setup key for manual entry
- one-time recovery codes that are displayed once

Setup does not complete until a valid TOTP code is entered and recovery codes are acknowledged.

## MFA / TOTP

MFA is mandatory for every admin account. The TOTP flow is compatible with:

- Google Authenticator
- Microsoft Authenticator
- Authy
- 1Password
- Bitwarden

Normal login requires:

1. username or email
2. password
3. TOTP code or an unused recovery code

Recovery codes are hashed in storage and are valid only once.

## Emergency Local Recovery

Break-glass commands are local operator tools. They do not destroy provider configuration, feed tokens, or sync history.

Reset an admin password:

```bash
docker compose exec web python -m calsync.cli reset-admin-password --identifier admin
```

Reset admin MFA and issue fresh recovery codes:

```bash
docker compose exec web python -m calsync.cli reset-admin-mfa --identifier admin
```

These same commands can be run directly on the host if the app dependencies are installed locally:

```bash
python -m calsync.cli reset-admin-password --identifier admin
python -m calsync.cli reset-admin-mfa --identifier admin
```

## Admin UI

Current admin pages:

- `/admin` for the dashboard, combined feed link, and last sync summary
- `/admin/flightboard` for the private Flightboard view of enabled calendar events
- `/admin/providers` for deployment-wide Google OAuth app settings
- `/admin/accounts` for mock, Google, and Apple/iCloud account connection
- `/admin/calendars` for provider calendar enable or disable actions
- `/admin/sync` for sync history and manual sync now actions
- `/admin/feeds` for combined ICS publishing and token rotation

These pages require admin login plus MFA-backed session establishment.

## Public App URL

CalSync can store a canonical external origin in `Provider Settings` under `Public App URL`.

Use this when:

- the deployment is reached through an HTTPS hostname instead of localhost
- Google OAuth should use a stable public callback URL even if the admin is browsing from a LAN IP or localhost
- generated external links should prefer the saved hostname

Real deployment example:

- `https://calsync.neonbutterfly.net`

Operator flow:

1. Open `/admin/providers`.
2. Save the canonical hostname in `Public App URL`.
3. Save or review the Google OAuth client settings on the same page.
4. Open `/admin/accounts`.
5. Use `Connect Google Account`.

When a valid `Public App URL` is saved, CalSync uses that hostname for the Google callback preview and consent flow instead of relying only on the current browser origin.

## Google OAuth Setup

Google OAuth setup is implemented and is tracked in issue `#2`.

Google OAuth setup requires:

- creating a Google Cloud project
- enabling the Google Calendar API
- creating OAuth web application client credentials
- saving the Google client ID and secret in `Provider Settings` inside the admin UI
- adding the CalSync callback URL derived from the saved `Public App URL`, `PUBLIC_BASE_URL`, or the request origin

Recommended Google Auth Platform setup:

1. In Google Cloud, open `Google Auth Platform`.
2. Configure `Branding` with an app name, support email, and contact email.
3. In `Audience`, choose:
   - `External` if you want to connect personal Gmail accounts or multiple unrelated Google accounts
   - `Internal` only if every Google account you will connect belongs to the same Google Workspace organization
4. If you use `External` while the app is still in testing mode, add every Google account you plan to connect as a test user.
5. In `Data Access`, add only the scopes CalSync needs:
   - `openid`
   - `email`
   - `profile`
   - `https://www.googleapis.com/auth/calendar.readonly`
6. In `Clients`, create a `Web application` OAuth client.
7. Add the CalSync redirect URI shown on the Provider Settings page.
8. Save the client ID and client secret into CalSync at `/admin/providers`.

Public hostname example for this deployment:

- `https://calsync.neonbutterfly.net/auth/google/callback`

How multiple Google accounts work:

- You only need one Google Cloud project and one OAuth web client for this CalSync deployment.
- That one OAuth client can be reused to connect multiple Google accounts.
- Each Google account still has to go through its own consent flow from `/admin/accounts`.
- CalSync stores each connected Google account separately after the user authorizes it.

Optional bootstrap fallback:

- operators may still set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in `.env`
- if no database-backed Google provider settings exist yet, CalSync will use those environment values as a fallback

Typical redirect URIs:

- `http://localhost:3080/auth/google/callback`
- `https://calendar.example.com/auth/google/callback`

Important Google limitation:

- Google does not allow raw LAN IP addresses such as `http://192.168.50.232:3080/auth/google/callback` as OAuth redirect URIs.

Practical meaning:

- The CalSync app itself still works on `http://SERVER-IP:3080` for normal LAN access.
- Google account connection works on `http://localhost:3080` when you complete the OAuth flow on the server machine itself.
- For remote browser-based Google account connection, save `Public App URL` in the admin UI or configure `PUBLIC_BASE_URL` to an HTTPS hostname or domain that is registered with Google.
- If your Google app is still in testing mode and requests `calendar.readonly`, every Google account you want to connect must be added as a test user first.

The Google integration is read-only and requests:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/calendar.readonly`

## Flightboard

CalSync includes a private admin-only Flightboard at `/admin/flightboard`.

The Flightboard:

- is visible only after admin login
- shows only current and upcoming enabled calendar events from the normalized local event store
- supports `Day`, `Week`, and `Month` ranges inside the private admin page
- converts UTC-backed event times into Alaska display time for the admin UI
- scrolls automatically for operations-style viewing while still allowing manual pause on hover
- never shows events that have already ended
- is intended as a scrolling operations-style board, not a public anonymous display
- stays separate from ICS publishing and does not create a new public route

Other admin-facing timestamp displays, including the dashboard and sync status page, also render event and sync times in Alaska local time with a consistent `AKST` label instead of raw UTC values.

## Apple App-Specific Password

Apple does not offer Google-style OAuth for iCloud Calendar. CalSync uses CalDAV with:

- Apple ID username
- Apple app-specific password

Apple/iCloud onboarding is available from `/admin/accounts`. Each Apple account is added individually with:

- an account label
- the Apple ID username or email
- an Apple app-specific password

The Apple integration remains read-only and uses CalDAV discovery before calendars can be enabled for aggregation.

## Port And Bind Configuration

CalSync is intended to bind on all interfaces by default:

- `APP_HOST=0.0.0.0`
- `APP_PORT=3080`

This allows both:

- `http://localhost:3080`
- `http://SERVER-IP:3080`

Use `PUBLIC_BASE_URL` when generated callback or feed URLs must prefer a stable external origin.

## LAN Notes

CalSync works on LAN without a reverse proxy. For access outside the trusted LAN, add TLS before broader exposure.

Headless and LAN deployments should verify:

- the server firewall allows the chosen `APP_PORT`
- the browser uses the same host or `PUBLIC_BASE_URL` that feed links and future OAuth callbacks will use
- Docker publishes the chosen port to the host

For Google OAuth specifically:

- raw LAN IP callback URIs are blocked by Google
- localhost callbacks are valid
- remote Google OAuth flows should use an HTTPS hostname in `PUBLIC_BASE_URL`

## Backup And Restore

See [docs/ops.md](docs/ops.md) for the fuller operator runbook.

At minimum, back up:

- the PostgreSQL database
- the `.env` file
- any deployment-specific Compose overrides

Restore requires:

1. restoring the database
2. restoring `.env`
3. starting the same app version or running migrations before use

## Known Limitations

- Google OAuth has a real upstream redirect restriction: raw LAN IP callback URIs are not accepted by Google, even though the CalSync app itself works on LAN IPs.
- The worker loop is intentionally simple and will be expanded with richer retry and provider-specific error handling in later phases.
- Apple/iCloud sync currently uses straightforward CalDAV discovery and event retrieval and may need provider-specific hardening for broader production use.
- Local HTTP mode is suitable for localhost and LAN use, but public internet exposure should add TLS and tighter network controls first.
