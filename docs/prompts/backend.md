# Backend Prompt Capture

- GitHub issue: `#32`
- Scope: first Apple-first ChatGPT app slice on top of a small CalSync-owned service for conversational calendar write-back

## Interpreted Requirements

- the first conversational scheduling slice should target the shared iCloud family calendar
- ChatGPT should create, edit, and cancel appointments through CalSync instead of talking to Apple directly
- the service should stay small and focused, but it must preserve normalized local appointment records and Apple event mappings
- the shared workspace should act as the operational brain while iCloud remains the family-visible destination
- the initial tool surface should stay narrow and mutation-focused so the experience is reliable before broader search, planning, or reminder automation ships
- the design should leave room for later Google intake, iCloud Reminders sync, structured medical metadata, and Alexa-style voice input

## Behavioral Boundaries

- this slice is Apple/iCloud-first, not a broad multi-provider conversational assistant
- Google inbound event ingestion is future work
- iCloud Reminders sync is future work
- public booking links and broader availability logic are future work
- the first conversational app should expose create, edit, cancel, and date-range list flows

## Phase Notes

- issue `#32` builds on the preserved write-capable legacy work from earlier CalSync slices, now archived on `legacy/pre-chatgpt-brain-reset`
- the owned service is the durable contract; ChatGPT should never mutate CalDAV directly
- iCloud remains the family-facing calendar of record for day-to-day visibility
- CalSync should keep audit history and local event mappings so the later family workspace can grow without redesigning this slice

## Implemented In This Slice

- FastAPI runtime with `GET /`, `GET /healthz`, appointment mutation routes, and date-range lookup
- `GET /api/appointments` for date-range appointment lookup
- `POST /api/appointments` for appointment creation
- `PATCH /api/appointments/{appointment_id}` for appointment edits
- `POST /api/appointments/{appointment_id}/cancel` for appointment cancellation
- local Postgres persistence for:
  - Apple calendar connection metadata
  - normalized appointments
  - appointment external links
  - audit entries
- Alembic bootstrap migration for the Apple-first schema
- Apple CalDAV adapter that writes `.ics` payloads directly to the configured iCloud calendar URL
- dedicated Cloudflare Worker project in `workers/edge-calsync`
- live Worker route on `edge-calsync.neonbutterfly.net/*`
- Cloudflare KV-backed channel hash validation for `chatgpt`, `shortcuts`, `alexa`, and `webhooks`

## Operational Expectations

- the service requires a configured writable Apple calendar before any mutation route can succeed
- the Apple account should use an app-specific password, not an interactive account password
- the service writes to one designated primary iCloud calendar in this first slice
- appointment changes should update the same Apple provider event rather than recreating a new one
- cancellations should delete the remote Apple event and mark the local record as `cancelled`

## Known Boundaries In Current Code

- no appointment search or availability lookup yet
- list is limited to explicit date windows, not free-form search
- no Google ingestion yet
- no iCloud Reminders sync yet
- no structured medical metadata API fields yet
- no ChatGPT Apps SDK wrapper yet; the Worker is the live edge, but the dedicated ChatGPT app layer is still future work

## Cloudflare Deployment Requirement

- GitHub issue: `#35`
- interpreted requirement: evaluate Cloudflare against the rebooted Apple-first service and choose the path that matches the current FastAPI plus Postgres plus Apple CalDAV architecture

Expected deployment behavior:

- publish through Cloudflare Tunnel first if we want Cloudflare in front of the current service
- keep `kayraspi` or another Linux host as the origin until the database is externalized
- do not force this repo into Pages
- do not treat the current codebase as a drop-in Workers deployment
- revisit Cloudflare Containers only after the database/runtime boundary is redesigned

## Cloudflare Edge Worker Requirement

- GitHub issue: `#36`
- interpreted requirement: add a dedicated ChatGPT-first Cloudflare Worker as a thin authenticated edge proxy in front of the Pi-hosted Apple-first origin service

Expected edge behavior:

- deploy a dedicated Worker on its own subdomain such as `edge-calsync.neonbutterfly.net`
- keep the actual scheduling brain on `https://calsync.neonbutterfly.net`
- expose create, update, cancel, and list appointment routes through the Worker
- treat ChatGPT as the first enabled channel
- keep the Worker non-human-facing and machine-only
- keep token source-of-truth on the Pi and sync token hashes into Cloudflare automatically

Current reality:

- the Worker is live on `edge-calsync.neonbutterfly.net`
- the Pi origin now supports the Worker-facing list contract
- the Pi stores channel tokens in `/home/kay/apps/calsync/.runtime/channel-tokens.json`
- Cloudflare KV currently holds the active channel hashes used by the Worker
