# Operations Guide

This guide covers the current Apple-first CalSync service tracked in issue `#32`.

## What This Service Does

- exposes a small API for appointment create, edit, and cancel
- stores normalized appointment records locally
- writes calendar mutations to one configured iCloud calendar through CalDAV
- keeps local audit entries for every mutation

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

## Local Validation

Run the automated checks:

```powershell
pytest -v
docker compose config
```

## API Summary

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
5. Verify:
   - `http://127.0.0.1:3080/healthz` on-host
   - `http://192.168.50.232:3080/healthz` over the network

## Cloudflare Publish Path

If we want Cloudflare in front of this service without changing the runtime shape:

- keep the existing Linux-host deployment
- publish the service with Cloudflare Tunnel
- point the public hostname at the origin service on `http://127.0.0.1:3080`

Current Cloudflare guidance for this repo is documented in `docs/cloudflare.md`.

Important boundary:

- do not treat this repo as a Pages project
- do not treat this repo as a drop-in Workers deployment
- only consider Cloudflare Containers after the database is moved out of the local Compose-only shape

## Current Deployment Blocker

The service can be deployed now, but successful Apple writes still require the real iCloud values:

- Apple username
- Apple app-specific password
- primary writable iCloud calendar URL

If the old deployment secrets are not available anymore, the safest recovery path is:

1. recover the old Apple username and calendar URL from preserved config or database metadata if possible
2. generate a fresh Apple app-specific password
3. place the new values into the remote `.env`
