# CalSync Operations

## Docker Bring-Up

1. Copy `.env.example` to `.env`
2. Set `SESSION_SECRET` and `ENCRYPTION_KEY`
3. Review `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, and any Google OAuth settings
4. Run `docker compose up --build`

For local rebuilds:

```bash
docker compose up --build
```

For detached startup:

```bash
docker compose up --build -d
docker compose ps
```

## Google OAuth Operator Notes

Set these values in `.env` before using Google account connection:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- optional `GOOGLE_OAUTH_SCOPES`
- optional `GOOGLE_OAUTH_REDIRECT_PATH`

Redirect URI examples:

- `http://localhost:3080/auth/google/callback`
- `https://calendar.example.com/auth/google/callback`

Important limitation:

- Google does not accept raw LAN IP callback URIs such as `http://192.168.50.232:3080/auth/google/callback`

If operators need to connect Google from another device on the LAN, they should set `PUBLIC_BASE_URL` to an HTTPS hostname or domain that is registered in Google Cloud.

## Backup

Back up the database with:

```bash
docker compose exec db pg_dump -U calsync -d calsync > calsync-backup.sql
```

Back up configuration with:

```bash
cp .env .env.backup
```

Recommended backup set:

- PostgreSQL dump
- `.env`
- any local deployment notes or Compose overrides

## Restore

Restore the database with:

```bash
docker compose exec -T db psql -U calsync -d calsync < calsync-backup.sql
```

Then restore `.env` and restart:

```bash
docker compose up --build
```

## Health Checks

The web service exposes:

- `GET /healthz`

Expected local check:

```bash
curl http://localhost:3080/healthz
```

## Local Emergency Procedures

Reset an admin password without destroying configuration:

```bash
docker compose exec web python -m calsync.cli reset-admin-password --identifier admin
```

Reset admin MFA and issue fresh recovery codes:

```bash
docker compose exec web python -m calsync.cli reset-admin-mfa --identifier admin
```

These commands preserve provider accounts, calendar selections, feed tokens, and sync state.

## Worker Notes

The worker uses the same database and settings as the web service and polls on the configured `SYNC_POLL_SECONDS` interval.

Current Phase 1 behavior:

- discovers and syncs any stored provider accounts
- records sync results in the database
- survives container restarts because state is persisted in PostgreSQL

Current Phase 2 addition:

- refreshes and syncs Google provider accounts through the same worker loop
