# CalSync

CalSync is being rebooted as an Apple-first conversational scheduling system.

The previous full CalSync application was preserved on the `legacy/pre-chatgpt-brain-reset` branch so we can still reference its provider work, write-back patterns, and earlier UI ideas without carrying that whole surface forward on `main`.

## Current focus

- ChatGPT app for Apple Calendar
- small owned service as the scheduling brain
- iCloud as the family-facing calendar target
- future expansion toward Google intake, iCloud Reminders sync, and richer family/medical appointment logic

## Working docs

- Design spec: [docs/superpowers/specs/2026-05-27-calsync-apple-calendar-chatgpt-app-design.md](docs/superpowers/specs/2026-05-27-calsync-apple-calendar-chatgpt-app-design.md)
- Cloudflare edge Worker design: [docs/superpowers/specs/2026-05-28-calsync-cloudflare-edge-worker-chatgpt-design.md](docs/superpowers/specs/2026-05-28-calsync-cloudflare-edge-worker-chatgpt-design.md)
- Reset plan: [docs/superpowers/plans/2026-05-27-calsync-legacy-archive-reset.md](docs/superpowers/plans/2026-05-27-calsync-legacy-archive-reset.md)
- Apple-first service plan: [docs/superpowers/plans/2026-05-28-calsync-apple-first-service-kayraspi-deploy.md](docs/superpowers/plans/2026-05-28-calsync-apple-first-service-kayraspi-deploy.md)
- Operations guide: [docs/ops.md](docs/ops.md)
- Cloudflare fit and bootstrap: [docs/cloudflare.md](docs/cloudflare.md)

## Current service slice

Issues `#32`, `#36`, `#38`, and `#39` are now backed by:

- FastAPI runtime on port `3080`
- Postgres-backed local appointment storage
- Alembic migrations
- Apple CalDAV write adapter for create, update, cancel, and list-backed lookup flows
- a first real scheduling console at `/` for create, edit, cancel, and upcoming-list workflows
- Local audit entries and appointment-to-provider event mapping
- A dedicated Cloudflare Worker in `workers/edge-calsync`
- Live ChatGPT-first edge hostname: `https://edge-calsync.neonbutterfly.net`
- Live Pi origin hostname: `https://calsync.neonbutterfly.net`
- a first Alexa custom-skill adapter on top of the same shared scheduling brain

### Endpoints

- `GET /`
- `GET /api/info`
- `GET /healthz`
- `GET /api/appointments`
- `POST /api/appointments`
- `PATCH /api/appointments/{appointment_id}`
- `POST /api/appointments/{appointment_id}/cancel`

### Web console

The root page now acts as the first family scheduling UX:

- polished create-appointment form
- upcoming 30-day appointment list
- edit flow for existing appointments
- cancel flow for existing appointments
- direct Apple calendar write-back through the same backend used by the API and Worker

### Worker routes

- `GET /v1/appointments`
- `POST /v1/appointments`
- `PATCH /v1/appointments/{appointment_id}`
- `POST /v1/appointments/{appointment_id}/cancel`
- `POST /alexa`

### Alexa skill slice

The first Alexa integration now lives beside the Worker:

- Worker voice route: `POST /alexa`
- interaction model: `workers/edge-calsync/alexa/interaction-model.json`
- first intents:
  - `CreateAppointmentIntent`
  - `ListAppointmentsIntent`
  - `AMAZON.HelpIntent`
  - `AMAZON.CancelIntent`
  - `AMAZON.StopIntent`
  - `AMAZON.FallbackIntent`

Current auth shape:

- the Alexa skill should send the CalSync `alexa` channel token as the linked access token
- the Worker also checks the configured Alexa skill ID allowlist in `ALEXA_ALLOWED_SKILL_IDS`
- the voice route stays disabled until `ENABLE_ALEXA=true`

### Request shape

`POST /api/appointments`

```json
{
  "title": "Dentist",
  "date": "2026-06-01",
  "start_time": "10:00",
  "end_time": "11:00",
  "timezone": "America/Anchorage",
  "all_day": false,
  "location": "Clinic",
  "notes": "Bring insurance card",
  "attendees_text": "Mom, Kayra"
}
```

The create response includes:

- local `appointment_id`
- local `status`
- Apple provider `provider_event_id`
- a user-facing status `message`

## Token management

Channel tokens are generated on the Pi-hosted origin and their hashes are stored in Cloudflare KV for Worker auth.

Current source-of-truth location on `kayraspi`:

- `/home/kay/apps/calsync/.runtime/channel-tokens.json`

Current channels:

- `chatgpt`
- `shortcuts`
- `alexa`
- `webhooks`

## Local development

1. Copy `.env.example` to `.env`.
2. Fill in the Apple/iCloud settings:
   - `APPLE_USERNAME`
   - `APPLE_APP_SPECIFIC_PASSWORD`
   - `APPLE_PRIMARY_CALENDAR_URL`
3. Choose a real `POSTGRES_PASSWORD`.
4. If you want Pi-driven Cloudflare KV sync from the app runtime, also fill in:
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_TOKEN_KV_NAMESPACE_ID`
5. Start the stack with Docker Compose.
6. Verify `http://127.0.0.1:3080/healthz`.
7. Open `http://127.0.0.1:3080/` for the scheduling console.
8. If you are preparing the Alexa slice, also set:
   - `ALEXA_ALLOWED_SKILL_IDS`
   - `ALEXA_DEFAULT_TIMEZONE`

The API will not create calendar events until the Apple settings are populated.

## Tracking

- Conversational Apple-first app slice: issue `#32`
- Cloudflare edge Worker slice: issue `#36`
- Alexa skill slice: issue `#38`
- First family scheduling UX: issue `#39`
- Legacy archive and clean reset: issue `#33`

## Legacy archive

If we need anything from the old system, use the `legacy/pre-chatgpt-brain-reset` branch as the source of truth for that implementation history.
