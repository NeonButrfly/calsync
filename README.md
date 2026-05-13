# CalSync

## Project Overview

CalSync is a self-hosted, read-only calendar aggregation service for Linux and Unix hosts. This Phase 1 foundation delivers a Dockerized FastAPI application with persistent storage, first-run admin setup, mandatory MFA with TOTP, mock provider sync, protected admin pages, background worker wiring, and read-only ICS publishing.

The application is designed for local and LAN-first operation:

- Default local URL: `http://localhost:3080`
- Default LAN URL: `http://SERVER-IP:3080`
- Default bind host: `APP_HOST=0.0.0.0`
- Default bind port: `APP_PORT=3080`
- Optional public URL override: `PUBLIC_BASE_URL`

## Current Phase 1 Scope

Implemented today:

- first-run admin setup with username or email, strong password, mandatory MFA, QR enrollment, and recovery codes
- password plus TOTP login for the admin UI
- local break-glass commands for `reset-admin-password` and `reset-admin-mfa`
- mock provider discovery and event import into the normalized event store
- combined read-only ICS feed publishing with stable tokens and token rotation
- protected admin dashboard, calendars management, sync status, and ICS publishing pages
- separate `web`, `worker`, and `db` services for Docker deployment

Not implemented yet:

- Google account connection and Google OAuth setup inside the app
- Apple/iCloud CalDAV connection inside the app
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

Current Phase 1 admin pages:

- `/admin` for the dashboard, combined feed link, and last sync summary
- `/admin/calendars` for provider calendar enable or disable actions
- `/admin/sync` for sync history and manual sync now actions
- `/admin/feeds` for combined ICS publishing and token rotation

These pages require admin login plus MFA-backed session establishment.

## Google OAuth Setup

Google OAuth setup is part of Phase 2 and is not wired into the UI yet. This README still captures the operator expectation so documentation stays aligned with the roadmap for issue `#1`.

Google OAuth setup will require:

- creating a Google Cloud project
- enabling the Google Calendar API
- creating OAuth client credentials
- adding the CalSync callback URL derived from `PUBLIC_BASE_URL` or the LAN host and `APP_PORT`

For LAN and headless Linux use, plan to register a redirect URI that matches the exact browser-facing origin, such as `http://SERVER-IP:3080/...`, or provide a stable `PUBLIC_BASE_URL` before enabling Google OAuth.

## Apple App-Specific Password

Apple does not offer Google-style OAuth for iCloud Calendar. Phase 3 will use CalDAV with:

- Apple ID username
- Apple app-specific password

Apple app-specific password support is not wired into the Phase 1 UI yet, but the final product direction is documented here to match issue `#1`.

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

- Phase 1 uses the mock provider for validation and does not yet include real Google or iCloud account connection flows.
- The worker loop is intentionally simple and will be expanded with richer retry and provider-specific error handling in later phases.
- Local HTTP mode is suitable for localhost and LAN use, but public internet exposure should add TLS and tighter network controls first.
