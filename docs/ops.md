# Operations Guide

This guide covers the current Apple-first CalSync service, first scheduling UX, and edge Worker tracked in issues `#32`, `#36`, and `#39`.

## What This Service Does

- exposes a small API for appointment create, edit, and cancel
- exposes a date-range appointment list API for Worker lookup flows
- exposes a professional web scheduling console at `/` for create, edit, cancel, and review
- stores normalized appointment records locally
- writes calendar mutations to one configured iCloud calendar through CalDAV
- keeps local audit entries for every mutation
- supports Cloudflare edge token management for channel auth

## Required Environment

Copy `.env.example` to `.env` and fill in:

- `APP_HOST`
- `APP_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `APPLE_ACCOUNT_LABEL`
- `APPLE_USERNAME`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_PRIMARY_CALENDAR_URL`
- `APPLE_PRIMARY_CALENDAR_NAME`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_TOKEN_KV_NAMESPACE_ID`
- `CHANNEL_TOKEN_RUNTIME_PATH`

Minimum production values that must be real:

- `POSTGRES_PASSWORD`
- `APPLE_USERNAME`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_PRIMARY_CALENDAR_URL`

## Local Run

1. Copy `.env.example` to `.env`.
2. Fill in the Apple and database values.
3. Start the stack:

```powershell
docker compose up --build -d
```

4. Confirm the API is healthy:

```powershell
curl http://127.0.0.1:3080/healthz
```

5. Confirm the service root responds:

```powershell
curl http://127.0.0.1:3080/
```

6. Open the scheduling console in a browser:

```text
http://127.0.0.1:3080/
```

7. Optionally bootstrap channel tokens:

```powershell
docker compose run --rm -v ${PWD}/.runtime:/app/.runtime api python scripts/manage_channel_tokens.py bootstrap --channels chatgpt,shortcuts,alexa,webhooks
```

## Local Validation

Run the automated checks:

```powershell
pytest -v
docker compose --env-file .env.example config
npm --prefix workers/edge-calsync test
```

## API Summary

## Web console summary

Root experience:

- `GET /`
- `POST /appointments`
- `GET /appointments/{appointment_id}/edit`
- `POST /appointments/{appointment_id}/edit`
- `POST /appointments/{appointment_id}/cancel`

Behavior:

- shows a clean create-appointment form
- lists the next 30 days of appointments from the local store
- edits and cancels the same Apple-backed appointment records used by the API
- is intended to be the first family-facing control surface instead of forcing operators to work from raw API calls

### Create appointment

`POST /api/appointments`

Required body fields:

- `title`
- `date`
- `start_time`
- `end_time`
- `timezone`

Optional body fields:

- `all_day`
- `location`
- `notes`
- `attendees_text`

### Update appointment

`PATCH /api/appointments/{appointment_id}`

Any writable appointment field may be sent.

### Cancel appointment

`POST /api/appointments/{appointment_id}/cancel`

This removes the Apple calendar event and marks the local appointment as `cancelled`.

### List appointments

`GET /api/appointments?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

This powers the Worker-side “look up before editing or cancelling” flow.

## Edge Worker summary

Live edge hostname:

- `https://edge-calsync.neonbutterfly.net`

Worker routes:

- `GET /v1/appointments`
- `POST /v1/appointments`
- `PATCH /v1/appointments/{appointment_id}`
- `POST /v1/appointments/{appointment_id}/cancel`

## Deployment Target

Current planned target:

- host: `kayraspi`
- address: `192.168.50.232`
- path: `/home/kay/apps/calsync`
- port: `3080`

## Remote Deploy Shape

1. Sync this repo state to the host.
2. Create `/home/kay/apps/calsync/.env` with real values.
3. Start the stack with Docker Compose.
4. Run migrations through the `migrate` service.
5. Bootstrap `.runtime/channel-tokens.json` on the host-backed volume if Worker auth is needed.
6. Verify:
   - `http://127.0.0.1:3080/healthz` on-host
   - `http://192.168.50.232:3080/healthz` over the network
   - `http://127.0.0.1:3080/` renders the scheduling console on-host
   - `GET /api/appointments` works on the public origin hostname
   - the edge Worker returns `401` without auth
   - the edge Worker can list, create, and cancel with the ChatGPT token

## Cloudflare Edge Notes

Current Cloudflare guidance for this repo is documented in `docs/cloudflare.md`.

Important boundary:

- do not move the Apple/Postgres backend into the Worker
- do use the Worker as the ChatGPT-first public edge surface
- keep raw tokens on the Pi and only store token hashes in Cloudflare KV

## Current follow-up item

The live edge path works today, but automatic Pi-to-Cloudflare token-hash sync still wants one more production nicety:

- a dedicated `CLOUDFLARE_API_TOKEN` in the Pi `.env` so `sync-cloudflare` can run directly on-host without a workstation-assisted sync
