# Operations Guide

This guide covers the current Apple-first CalSync service, family scheduling UX, live Apple calendar sync, edge Worker, Alexa adapter, readiness surface, and Alexa setup flow tracked in issues `#32`, `#36`, `#38`, `#39`, `#40`, `#41`, `#43`, and `#45`.

## What This Service Does

- exposes a small API for appointment detail, create, edit, and cancel
- exposes a date-range appointment list API for Worker lookup flows
- exposes a professional web scheduling workspace at `/` for create, edit, cancel, filtered browsing, and review
- stores normalized appointment records locally
- syncs existing Apple calendar events into the local scheduling brain for requested date windows
- writes calendar mutations to one configured iCloud calendar through CalDAV
- keeps local audit entries for every mutation
- supports Cloudflare edge token management for channel auth
- reads the Pi-hosted `.runtime/channel-tokens.json` source-of-truth through an API-container bind mount

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
- `DEFAULT_TIMEZONE`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_TOKEN_KV_NAMESPACE_ID`
- `CHANNEL_TOKEN_RUNTIME_PATH`
- `EDGE_BASE_URL`
- `ALEXA_ALLOWED_SKILL_IDS`
- `ALEXA_DEFAULT_TIMEZONE`

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
- `GET /alexa/setup`
- `POST /appointments`
- `GET /appointments/{appointment_id}/edit`
- `POST /appointments/{appointment_id}/edit`
- `POST /appointments/{appointment_id}/cancel`

Behavior:

- shows a clean create-appointment form
- browses appointments by day, week, or month
- syncs the requested Apple calendar date window before rendering the schedule
- hides cancelled appointments from the default active schedule views while allowing a reference toggle when you intentionally want historical cancelled items
- shows a full-stack readiness panel for Apple, channel tokens, edge reachability, and Alexa setup state
- exposes an in-product Alexa setup page with a live package download instead of forcing repo-only setup
- shows a selected appointment detail panel with audit activity and provider metadata
- edits and cancels the same Apple-backed appointment records used by the API
- is intended to be the first family-facing control surface instead of forcing operators to work from raw API calls

### Alexa setup page

- `GET /alexa/setup`
- `GET /alexa/skill-package.zip`

This operator-facing flow now serves:

- the live edge Alexa endpoint
- the public privacy and terms URLs
- the current readiness state
- a downloadable Alexa custom skill package zip from the running app

### Readiness snapshot

`GET /api/readiness`

This returns a safe operator-facing summary of:

- Apple calendar write-readiness on the origin
- local channel-token presence for `chatgpt`, `shortcuts`, `alexa`, and `webhooks`
- edge Worker reachability
- edge channel enablement
- Alexa allowlist and enablement status
- the next recommended operator action

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

It now also syncs the requested Apple date range into the local appointment store so existing family-calendar events can be listed, edited, cancelled, and used by Alexa.

Default behavior hides cancelled appointments from active list views. To include them for reference, call:

`GET /api/appointments?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&include_cancelled=true`

### Appointment detail

`GET /api/appointments/{appointment_id}`

This returns the selected appointment, provider metadata, and local audit trail that powers the richer workspace detail view.

## Edge Worker summary

Live edge hostname:

- `https://edge-calsync.neonbutterfly.net`

Worker routes:

- `GET /status`
- `GET /v1/appointments`
- `GET /v1/appointments/{appointment_id}`
- `POST /v1/appointments`
- `PATCH /v1/appointments/{appointment_id}`
- `POST /v1/appointments/{appointment_id}/cancel`
- `POST /alexa`

## Alexa skill summary

Current voice route:

- `POST /alexa`

Current interaction model:

- `workers/edge-calsync/alexa/interaction-model.json`
- `workers/edge-calsync/alexa/skill-package/interactionModels/custom/en-US.json`

Current skill package:

- `workers/edge-calsync/alexa/skill-package/skill.json`
- `workers/edge-calsync/alexa/README.md`

Supported first intents:

- `CreateAppointmentIntent`
- `ListAppointmentsIntent`
- `NextAppointmentIntent`
- `CancelAppointmentIntent`
- `RescheduleAppointmentIntent`
- `AMAZON.HelpIntent`
- `AMAZON.CancelIntent`
- `AMAZON.StopIntent`
- `AMAZON.FallbackIntent`

Current auth shape:

- the Worker verifies incoming Alexa web-service requests using the Amazon certificate and request-signature flow
- the Worker only accepts configured skill IDs from `ALEXA_ALLOWED_SKILL_IDS`
- the route stays disabled until `ENABLE_ALEXA=true`

Current readiness support:

- `GET /status` is intentionally public and returns a safe readiness summary only
- it exposes enabled-channel flags, token-hash presence flags, and Alexa allowlist readiness without revealing any secrets

Current scope:

- create an appointment through the shared scheduling brain
- read appointments for a requested day
- read the next upcoming appointment in the next 30 days
- cancel a matching appointment by title and date
- reschedule a matching appointment to a new day or time
- keep all actual calendar writes in the origin service
- rely on the origin's live Apple date-range sync so pre-existing family-calendar events can be surfaced to voice flows

Operator setup:

1. Create or import the custom skill package from `workers/edge-calsync/alexa/skill-package`.
2. After Alexa generates the real skill ID, set that ID in `ALEXA_ALLOWED_SKILL_IDS`.
3. Set `ENABLE_ALEXA=true`.
4. Redeploy the Worker.
5. Confirm the public policy URLs are reachable:
   - `https://calsync.neonbutterfly.net/privacy`
   - `https://calsync.neonbutterfly.net/terms`

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
6. Keep the host `.runtime` directory in place, because the API container now mounts it at `/app/.runtime` for readiness and channel-token operations.
7. Verify:
   - `http://127.0.0.1:3080/healthz` on-host
   - `http://192.168.50.232:3080/healthz` over the network
   - `http://127.0.0.1:3080/` renders the scheduling console on-host
   - `GET /api/readiness` shows the same channel-token presence that exists in `/home/kay/apps/calsync/.runtime/channel-tokens.json`
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
