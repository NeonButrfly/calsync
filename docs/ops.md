# CalSync Operations

## Docker Bring-Up

1. Copy `.env.example` to `.env`
2. Set `SESSION_SECRET` and `ENCRYPTION_KEY`
3. Review `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, and the provider onboarding plan for Google and Apple accounts
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

Set these values in `.env` only if you want bootstrap fallback credentials before signing in to the admin UI:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- optional `GOOGLE_OAUTH_SCOPES`
- optional `GOOGLE_OAUTH_REDIRECT_PATH`

Normal operator flow:

1. sign in to CalSync
2. open `/admin/providers`
3. save the shared Google OAuth client ID and secret there
4. open `/admin/accounts`
5. connect one or more Google accounts

Redirect URI examples:

- `http://localhost:3080/auth/google/callback`
- `https://calendar.example.com/auth/google/callback`

Important limitation:

- Google does not accept raw LAN IP callback URIs such as `http://192.168.50.232:3080/auth/google/callback`

If operators need to connect Google from another device on the LAN, they should set `PUBLIC_BASE_URL` to an HTTPS hostname or domain that is registered in Google Cloud.

## Apple / iCloud Operator Notes

Apple/iCloud onboarding is account-based, not deployment-based.

For each Apple account:

1. open `/admin/accounts`
2. enter an account label
3. enter the Apple ID username or email
4. enter an app-specific password
5. submit the form to discover calendars

The Apple credentials are encrypted at rest in the CalSync database.

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
- encrypted Google provider settings and encrypted Apple app-specific passwords inside the CalSync database
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
- refreshes and syncs Apple/iCloud CalDAV accounts through the same worker loop
