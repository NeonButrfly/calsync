# Operations Guide

This guide covers the current CalSync service, family scheduling UX, the planner-style day/week/month schedule board, a first public booking page, public booking invitee contact capture, in-product booking setup, public booking availability rules, multiple public booking types with shareable links, a public booking catalog chooser, in-product booking type management actions, truthful blocked booking-setup actions for no-calendar states, truthful blocked Google and Microsoft browser-connect actions before OAuth setup exists, truthful Google and Microsoft shared next-action summaries before OAuth setup exists, live Apple calendar sync, writable Google and Microsoft setup, multi-calendar Apple targets, provider-aware Alexa calendar targeting, availability lookup, edge Worker, remote MCP Worker, Alexa adapter, readiness surface, Apple setup flow, safe Apple setup validation before reconnect save, Alexa setup flow, persisted desired Alexa edge settings, truthful save-only Alexa action labels before Worker access exists, restore-aware readiness guidance for recovery-shaped deployments, legacy Pi-backup import for Apple recovery hints, one-step loading of recovered Apple hints into the setup form, automatic default loading of the recommended Apple recovery hint, shared Apple recovery guidance aligned with the already-loaded reconnect state, recovery-aware Apple reconnect messaging, recovery-aware Apple hint ranking that prefers true writable booking targets, recovery-aware Apple reconnect actions on blocked operator surfaces, recovery-aware Apple reconnect guidance across blocked root workspace panels, recovery-aware Alexa guidance aligned with Apple reconnect, recovery-aware booking setup guidance across target behavior and blocked save/create actions, recovery-aware root capability-summary guidance aligned with Apple reconnect, recovery-aware Alexa simulator guidance aligned with Apple reconnect, recovery-aware Alexa simulator selector guidance aligned with Apple reconnect, recovery-aware public booking guidance aligned with Apple reconnect, recovery-aware public booking submit errors aligned with Apple reconnect, recovery-aware root appointment submit errors aligned with Apple reconnect, recovery-aware stale appointment edit and cancel routes aligned with Apple reconnect, recovery-aware appointment update and cancel API errors aligned with Apple reconnect, recovery-aware Alexa scheduling errors aligned with Apple reconnect, recovery-aware Alexa read intents aligned with Apple reconnect, recovery-aware Alexa launch/help/fallback guidance aligned with Apple reconnect, voice-specific next guidance for Alexa setup and Connections voice panels, shared Alexa account-linking readiness on Connections, truthful desired Alexa-state messaging on Connections, shared Alexa writable-calendar readiness on Connections, Alexa Step 4 prerequisite visibility, Alexa Step 4 writable-calendar visibility, Alexa Step 4 Cloudflare-access visibility, Alexa Step 4 desired-settings visibility, simulator readiness guidance for missing connected calendar states, in-product writable target verification, encrypted operator-settings backup and restore from `/connections`, the checklist-style Connections verification center, direct provider actions from that shared surface, truthful workspace capability messaging, blocked root create guidance for no-calendar states, blocked root availability guidance for no-calendar states, blocked public-booking availability guidance for no-calendar states, blocked root schedule-sync guidance for no-calendar states, blocked root hero/detail truthfulness for stale local appointment rows, and truthful Apple setup empty-state guidance for no-account states tracked in issues `#3`, `#17`, `#31`, `#32`, `#36`, `#37`, `#38`, `#39`, `#40`, `#41`, `#43`, `#45`, `#46`, `#47`, `#48`, `#49`, `#50`, `#51`, `#52`, `#53`, `#54`, `#55`, `#56`, `#57`, `#58`, `#59`, `#60`, `#61`, `#62`, `#63`, `#64`, `#65`, `#66`, `#67`, `#68`, `#69`, `#70`, `#71`, `#72`, `#73`, `#74`, `#75`, `#76`, `#77`, `#78`, `#79`, `#80`, `#81`, `#82`, `#83`, `#84`, `#85`, `#86`, `#87`, `#88`, `#89`, `#90`, `#91`, `#92`, `#93`, `#94`, `#95`, `#96`, `#97`, `#98`, `#99`, `#100`, `#101`, `#102`, `#103`, `#104`, `#105`, and `#106`.

## What This Service Does

- exposes a small API for appointment detail, create, edit, and cancel
- exposes a date-range appointment list API for Worker lookup flows
- exposes a shared availability API for open-slot lookup
- exposes a professional web scheduling workspace at `/` for create, edit, cancel, filtered browsing, and review
- exposes a planner-style day/week/month board at `/` so the selected schedule horizon changes the actual presentation layer
- exposes a first public booking page at `/book` so invitees can request open time through the same shared write-capable scheduling brain
- exposes public booking requester contact capture so invitees can say who is requesting the time and how to reach them
- exposes an in-product booking setup page at `/booking/setup` so operators can control the public booking title, description, duration defaults, search window, success copy, and writable target
- exposes public booking availability rules so operators can restrict `/book` to chosen weekdays and daily booking hours
- exposes multiple public booking types so `/book/{slug}` can represent different appointment flows with separate invitee-facing copy and defaults
- exposes a public booking catalog so `/book` becomes a chooser when more than one public booking type exists
- exposes in-product booking type management so operators can make a type the default or delete a stale public link from `/booking/setup`
- exposes a connections workspace at `/connections` so Apple, Google, and Microsoft setup can be reviewed together
- exposes a checklist-style verification center at `/connections` so provider readiness and last write proof can be reviewed together
- exposes direct Google and Microsoft refresh/disconnect actions from `/connections` so the shared control surface is not just read-only
- exposes Alexa launch state and quick edge-setting controls from `/connections` so the shared control surface can drive the last-mile voice setup too
- uses restore-aware readiness guidance when only non-provider settings remain, so the workspace and Connections page can point operators toward encrypted restore instead of implying fresh provider onboarding is the only sensible next step
- exposes a legacy Pi-backup import path on `/connections` so the preserved SQL dump can recover Apple account and calendar hints into the product without manual database inspection
- exposes one-step loading of recovered Apple hints into the setup form so `/calendar/setup` can start from the imported account and calendar values instead of forcing operators to retype them
- auto-loads the recommended recovered Apple hint into `/calendar/setup` when no Apple account is connected yet, so recovery mode opens straight into the Family reconnect path by default
- keeps shared readiness and Connections Apple guidance aligned with that auto-loaded recovery flow, so those surfaces no longer tell operators to perform a redundant manual hint-load step
- exposes recovery-aware Apple reconnect guidance across `/`, `/connections`, and `/calendar/setup` so imported legacy hints lead directly to the next real reconnect step
- keeps blocked operator surfaces on `/` and `/booking/setup` aligned with that Apple recovery flow, so the main workspace and booking setup point directly at Apple reconnect when it is the real next step
- keeps the booking setup target-behavior card plus blocked save and booking-type creation responses aligned with that same Apple recovery flow, so the full operator path uses one reconnect message instead of mixing recovery-aware and generic copy
- keeps the root `What works today` capability summary aligned with that same Apple recovery flow, so the sidebar no longer falls back to blank-install writable-calendar wording while the rest of the workspace is recovery-aware
- keeps the Alexa simulator readiness panel aligned with that same Apple recovery flow, so `/alexa/simulator` no longer falls back to blank-install no-calendar wording while the rest of the voice setup path is recovery-aware
- keeps the Alexa simulator empty selector helper text aligned with that same Apple recovery flow, so missing named-calendar options now point operators to Apple reconnect instead of blank-install setup wording
- keeps the public booking page aligned with that same Apple recovery flow, so blocked invitee-facing availability, request-state, and target-card copy now point to Apple reconnect instead of blank-install no-calendar wording
- keeps blocked public booking submit responses aligned with that same Apple recovery flow, so direct invitee request attempts no longer fall back to a stale generic no-target error
- keeps blocked root appointment-create submit responses aligned with that same Apple recovery flow, so direct schedule-workspace write attempts no longer fall back to a raw Apple config error
- keeps stale deep-link appointment edit and cancel routes aligned with that same Apple recovery flow, so recovery-mode direct editor URLs no longer expose a real edit form or a raw missing-target error
- keeps recovery-mode appointment update and cancel API routes aligned with that same Apple recovery flow, so direct API callers no longer get the raw Apple target lookup failure on stale local rows
- keeps blocked Alexa scheduling responses aligned with that same Apple recovery flow, so simulator and live voice scheduling intents no longer speak a raw Apple config error
- keeps blocked Alexa read intents aligned with that same Apple recovery flow, so simulator and live voice list, next, availability, cancel, and reschedule flows no longer leak stale local rows or generic search fallbacks while Apple reconnect is still required
- keeps Alexa launch, help, and fallback guidance aligned with that same Apple recovery flow, so the public simulator no longer coaches blocked calendar reads or writes while Apple reconnect is still required
- keeps the root workspace default-target card aligned with that same Apple recovery flow, so the main schedule surface shows the loaded recovered Apple target instead of `No calendar selected` when reconnect is still blocked
- keeps blocked root and booking-setup target selectors aligned with that same Apple recovery flow, so disabled picker states name the loaded recovered Apple target instead of falling back to `No writable calendars connected yet`
- keeps the blocked root schedule, detail, create, and availability panels aligned with that same Apple recovery flow, so the main workspace no longer mixes recovery-aware readiness with generic no-calendar panel copy
- keeps Alexa setup and the Connections voice panel aligned with that same Apple recovery flow, so voice turn-on guidance now points at the real recovered-calendar prerequisite when Apple reconnect is the current blocker
- exposes voice-specific next guidance for Alexa setup and Connections voice panels so those flows explain the real voice turn-on work instead of inheriting generic provider-readiness copy
- exposes Alexa account-linking readiness on `/connections` so the shared voice panel shows whether the household link code is already configured
- keeps the shared Alexa desired-settings card on `/connections` truthful, so unsaved defaults do not read like a real saved voice plan
- exposes writable-calendar readiness on `/connections` for the Alexa panel so the shared voice surface shows the first real schedule prerequisite too
- keeps the shared Alexa live-route card on `/connections` truthful, so it reflects the real blocker order instead of acting like route enablement is the only missing step when the real skill ID or Cloudflare access still comes first
- keeps the shared Google and Microsoft next-action summary on `/connections` truthful, so missing OAuth setup is surfaced before browser account connect is suggested
- exposes account-linking readiness directly in Alexa Step 4 so the final live turn-on summary no longer hides that prerequisite
- exposes writable-calendar readiness directly in Alexa Step 4 so the final live turn-on summary shows the first real scheduling blocker alongside the edge and auth prerequisites
- exposes Cloudflare Worker access readiness directly in Alexa Step 4 so the final live turn-on summary also shows whether product-managed Worker updates can run from the current deployment
- exposes desired Alexa-state readiness directly in Alexa Step 4 so the final live turn-on summary shows whether CalSync has a saved voice plan before operators expect live edge changes to apply
- exposes simulator readiness guidance for missing connected calendar states so `/alexa/simulator` explains when LaunchRequest is still useful and why scheduling intents are not yet meaningful
- exposes encrypted operator-settings backup and restore from `/connections` so the product-vault setup can be exported and recovered with the same deployment encryption key
- surfaces recovered legacy Apple hints on `/calendar/setup` so operators can finish Apple restoration with a fresh app-specific password instead of guessing old calendar URLs
- lets operators load a recovered Apple calendar hint directly into the `/calendar/setup` form before saving a fresh app-specific password
- exposes `POST /connections/legacy-backup/import` for that legacy Apple-hint recovery flow
- stores normalized appointment records locally
- syncs existing Apple calendar events and connected Google or Microsoft calendar events into the local scheduling brain for requested date windows
- writes calendar mutations to one selected connected calendar target through CalDAV, Google Calendar, or Microsoft Graph
- can run a safe create, update, and cancel smoke test against one selected writable calendar target from inside the product
- keeps local audit entries for every mutation
- supports Cloudflare edge token management for channel auth
- exposes a remote authenticated MCP endpoint for ChatGPT-style tool access
- reads the Pi-hosted `.runtime/channel-tokens.json` source-of-truth through an API-container bind mount

## Required Environment

Copy `.env.example` to `.env` and fill in:

- `APP_HOST`
- `APP_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `ENCRYPTION_KEY`
- `APPLE_ACCOUNT_LABEL`
- `APPLE_USERNAME`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `APPLE_PRIMARY_CALENDAR_URL`
- `APPLE_PRIMARY_CALENDAR_NAME`
- `DEFAULT_TIMEZONE`
- optional Google setup now lives in-product through:
  - `GET /google/setup`
  - `GET /auth/google/start`
  - `GET /auth/google/callback`
- optional Microsoft setup now lives in-product through:
  - `GET /microsoft/setup`
  - `GET /auth/microsoft/start`
  - `GET /auth/microsoft/callback`
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
- `GET /booking/setup`
- `GET /book`
- `GET /book/{slug}`
- `GET /connections`
- `GET /connections/settings-backup`
- `POST /booking/setup/types/default`
- `POST /booking/setup/types/delete`
- `POST /connections/test`
- `POST /connections/alexa`
- `POST /connections/settings-restore`
- `POST /connections/google/refresh`
- `POST /connections/google/disconnect`
- `POST /connections/microsoft/refresh`
- `POST /connections/microsoft/disconnect`
- `GET /calendar/setup`
- `POST /calendar/setup`
- `POST /calendar/setup/validate`
- `POST /calendar/setup/calendars`
- `GET /google/setup`
- `POST /google/setup`
- `GET /auth/google/start`
- `GET /auth/google/callback`
- `GET /microsoft/setup`
- `POST /microsoft/setup`
- `POST /microsoft/setup/refresh`
- `POST /microsoft/setup/disconnect`
- `GET /auth/microsoft/start`
- `GET /auth/microsoft/callback`
- `GET /alexa/setup`
- `POST /alexa/setup`
- `POST /alexa/setup/account-linking`
- `GET /alexa/account-linking/authorize`
- `POST /alexa/account-linking/authorize`
- `GET /alexa/simulator`
- `POST /alexa/simulator`
- `POST /api/alexa/account-linking/validate`
- `POST /appointments`
- `GET /appointments/{appointment_id}/edit`
- `POST /appointments/{appointment_id}/edit`
- `POST /appointments/{appointment_id}/cancel`

Behavior:

- shows a clean create-appointment form
- lets operators choose a target connected calendar for create and edit when multiple writable Apple, Google, or Microsoft targets are available
- browses appointments by day, week, or month
- syncs the requested connected calendar date window before rendering the schedule
- hides cancelled appointments from the default active schedule views while allowing a reference toggle when you intentionally want historical cancelled items
- shows a full-stack readiness panel for Apple, channel tokens, edge reachability, and Alexa setup state
- exposes a dedicated Connections page that summarizes Apple, Google, and Microsoft setup in one place before the operator dives into provider-specific forms
- exposes a checklist-driven Connections page that persists last write proof for each writable target and can rerun that proof directly from one place
- exposes shared Google and Microsoft account actions from that same Connections page so operators can connect, refresh, or disconnect without bouncing into a different workflow for routine tasks
- exposes Alexa desired-vs-live edge state plus a quick apply form from that same Connections page so operators can save or push voice turn-on settings without leaving the shared control surface
- exposes a root schedule board that now renders distinct day, week, and month planning states instead of only a single agenda layout
- exposes a root workspace capability summary that now reflects the actual connected readiness state instead of static broad capability copy
- exposes a blocked root create state when no writable calendar is connected, so the schedule workspace points operators toward setup instead of implying write actions are already available
- exposes a blocked root availability state when no writable calendar is connected, so the schedule workspace points operators toward setup instead of implying there are simply no open windows
- exposes a blocked root schedule-sync state when no writable calendar is connected, so the schedule board and detail pane do not read like a normal empty calendar
- keeps the disconnected root hero and selected-detail surfaces blocked too, so stale local appointment rows do not make the workspace look partially live when no writable calendar is connected
- exposes a truthful Apple setup empty state when no Apple account is connected, so `/calendar/setup` does not show a fake connected-account summary or add-calendar controls before the first Apple account exists
- exposes a first public booking page that searches open time and creates a real appointment on the default writable connected calendar target
- exposes public booking requester contact fields so the saved appointment context records who asked for the time and how to follow up
- exposes an in-product booking setup page that lets operators configure the invitee-facing copy, default duration, search horizon, success message, and chosen writable target for `/book`
- exposes public booking weekday and hour rules so `/book` only suggests openings inside the operator-managed bookable window
- exposes a blocked public-booking availability state when no writable calendar is connected, so `/book` does not look like live invitee scheduling before the provider path is actually ready
- exposes a blocked booking-setup state when no writable calendar is connected, so `/booking/setup` does not pretend disconnected save and booking-type creation actions are ready
- exposes multiple public booking types so operators can create and share distinct invitee-facing URLs like `/book/school-intake` without reusing one global booking configuration
- exposes a booking-type chooser at `/book` when more than one public booking type exists, while keeping direct `/book/{slug}` flows for focused links
- exposes direct booking-type management actions so operators can make one type the default `/book` flow or delete a stale type without leaving `/booking/setup`
- exposes an in-product Apple calendar setup page with encrypted vault-backed storage instead of forcing host-only Apple env edits
- exposes an in-product Google setup page with encrypted vault-backed OAuth storage plus browser-based account connect
- exposes an in-product Microsoft setup page with encrypted vault-backed OAuth storage plus browser-based account connect
- exposes truthful blocked Google and Microsoft browser-connect actions until the shared OAuth app has been saved, so setup pages and `/connections` do not advertise a known `400` path
- exposes an in-product Alexa setup page with a live package download instead of forcing repo-only setup
- can read and update the edge Worker Alexa flags from the setup page when Cloudflare worker-management permission is configured
- exposes an in-product Alexa simulator page that previews the real Worker voice logic before the Amazon-side turn-on is finished
- exposes an open-time finder in the root workspace for fast gap discovery
- shows a selected appointment detail panel with audit activity and provider metadata
- edits and cancels the same Apple-backed, Google-backed, or Microsoft-backed appointment records used by the API
- is intended to be the first family-facing control surface instead of forcing operators to work from raw API calls

### Apple calendar setup page

- `GET /calendar/setup`
- `POST /calendar/setup`

This operator-facing flow now serves:

- Apple account label
- Apple username
- Apple app-specific password
- Apple primary calendar URL
- Apple primary calendar name
- more than one connected Apple account
- additional tracked Apple calendar targets
- one default Apple calendar target for new appointments
- a safe validation action that tests fresh Apple credentials and calendar access before save

Current management boundary:

- the product can use either deployment env Apple settings or product-vault Apple settings
- product-vault Apple settings are encrypted with `ENCRYPTION_KEY`
- the appointment service and readiness surface now fall back to those saved product settings when host env Apple values are absent
- `POST /calendar/setup/validate` can run a safe read probe against the entered Apple username, app-specific password, and calendar URL without mutating the saved product-vault Apple state
- imported legacy Apple recovery hints now prefer explicit `writable_booking_target` calendars over generic enabled personal-reference calendars when choosing the recommended reconnect target
- `POST /calendar/setup/calendars` can add another saved Apple target for a selected Apple account without replacing the existing default target
- the calendar setup page remains the place to define the default target Apple calendar for the family-facing Apple path
- each saved Apple target can also run an in-product write smoke test to prove that target really supports create, update, and cancel

### Google setup page

- `GET /google/setup`
- `POST /google/setup`
- `GET /auth/google/start`
- `GET /auth/google/callback`

This operator-facing flow now serves:

- the shared Google OAuth client ID and secret for this deployment
- browser-based account connect on the live CalSync domain
- encrypted refresh-token storage in the product vault
- multiple connected Google accounts under the same shared OAuth app
- discovered Google calendar targets that can feed the same target picker used by the workspace
- a refresh action that resyncs one connected Google account email and discovered calendars from the live Google API
- a disconnect action that clears one linked Google account and its calendar catalog while preserving the shared OAuth client

Current management boundary:

- the product stores the shared Google client ID, client secret, connected account label/email, refresh token, and discovered Google calendar catalogs encrypted with `ENCRYPTION_KEY`
- writable Google targets appear in the same picker used for `POST /appointments` and `POST /appointments/{appointment_id}/edit`
- Google mutations and date-range reads now run through the same shared appointment service instead of a separate product path
- disconnecting one Google account keeps the deployment-wide OAuth client in place so the operator can reconnect without re-entering the client ID and secret
- each discovered Google target can run an in-product write smoke test to prove the connected account and calendar are truly writable

### Microsoft setup page

- `GET /microsoft/setup`
- `POST /microsoft/setup`
- `GET /auth/microsoft/start`
- `GET /auth/microsoft/callback`

This operator-facing flow now serves:

- the shared Microsoft OAuth client ID and secret for this deployment
- browser-based account connect on the live CalSync domain
- encrypted refresh-token storage in the product vault
- multiple connected Microsoft accounts under the same shared OAuth app
- discovered Microsoft calendar targets that can feed the same target picker used by the workspace
- a refresh action that resyncs one connected Microsoft account email and discovered calendars from the live Microsoft Graph API
- a disconnect action that clears one linked Microsoft account and its calendar catalog while preserving the shared OAuth client

Current management boundary:

- the product stores the shared Microsoft client ID, client secret, connected account label/email, refresh token, and discovered Microsoft calendar catalogs encrypted with `ENCRYPTION_KEY`
- writable Microsoft targets appear in the same picker used for `POST /appointments` and `POST /appointments/{appointment_id}/edit`
- Microsoft mutations and date-range reads now run through the same shared appointment service instead of a separate product path
- disconnecting one Microsoft account keeps the deployment-wide OAuth client in place so the operator can reconnect without re-entering the client ID and secret
- each discovered Microsoft target can run an in-product write smoke test to prove the connected account and calendar are truly writable

### Alexa setup page

- `GET /alexa/setup`
- `POST /alexa/setup`
- `GET /alexa/simulator`
- `GET /alexa/skill-package.zip`

This operator-facing flow now serves:

- the live edge Alexa endpoint
- the public privacy and terms URLs
- the current readiness state
- a downloadable Alexa custom skill package zip from the running app
- a Cloudflare Worker access form for:
  - `CLOUDFLARE_ACCOUNT_ID`
  - `CLOUDFLARE_API_TOKEN`
- a desired Alexa edge-state summary that shows what CalSync has saved versus what the live Worker is currently doing
- edge Worker controls for:
  - `ENABLE_ALEXA`
  - `ALEXA_ALLOWED_SKILL_IDS`

Current management boundary:

- the setup page can use either deployment env credentials or product-vault credentials saved from the setup page
- product-vault credentials are encrypted with `ENCRYPTION_KEY`
- the desired Alexa state is also saved in the product vault, encrypted at rest with `ENCRYPTION_KEY`
- the setup page now keeps a save-now/apply-later path, so operators can persist the intended Alexa enablement and skill allowlist even when Cloudflare Worker management is not configured yet
- when Worker management is unavailable, both `/alexa/setup` and `/connections` switch to truthful save-only action labels instead of implying a live apply path that cannot run yet
- the setup page shows live-versus-desired drift clearly instead of failing as an opaque one-shot control surface
- the configured token must include `Workers Scripts Write`
- if the token only has KV permissions, the product shows a clear permission error instead of pretending the edge Worker can be managed

### Alexa simulator page

- `GET /alexa/simulator`
- `POST /alexa/simulator`

This operator-facing flow now:

- builds a voice test request from a simple form with provider-aware calendar targets drawn from the shared scheduling brain
- sends it through the real edge Alexa simulation route using the live ChatGPT channel token
- shows the spoken response, session-ending behavior, and raw Alexa response JSON
- helps validate the live voice logic before `ENABLE_ALEXA=true` and the final skill-ID allowlist turn-on

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
- `target_calendar_url`

### Update appointment

`PATCH /api/appointments/{appointment_id}`

Any writable appointment field may be sent.

This now includes `target_calendar_url`, which lets the update flow move an appointment from one saved Apple calendar target to another or into a connected Google or Microsoft calendar target.

### Cancel appointment

`POST /api/appointments/{appointment_id}/cancel`

This removes the Apple calendar event and marks the local appointment as `cancelled`.

### List appointments

`GET /api/appointments?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

This powers the Worker-side “look up before editing or cancelling” flow.

It now also syncs the requested provider date range into the local appointment store across the saved Apple calendar targets and connected Google or Microsoft calendars, so existing calendar events can be listed, edited, cancelled, and used by Alexa.

Default behavior hides cancelled appointments from active list views. To include them for reference, call:

`GET /api/appointments?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&include_cancelled=true`

### Availability lookup

`GET /api/availability?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&duration_minutes=60`

This returns the first matching open windows from the connected-calendar schedule using the same synced appointment inventory as the workspace and Alexa.

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
- `GET /v1/availability`
- `POST /v1/appointments`
- `PATCH /v1/appointments/{appointment_id}`
- `POST /v1/appointments/{appointment_id}/cancel`
- `POST /alexa`
- `POST /alexa/simulate`

## MCP Worker summary

Live MCP hostname:

- `https://mcp-calsync.neonbutterfly.net`

Workers.dev MCP fallback:

- `https://mcp-calsync.kaymayers9.workers.dev`

Worker route:

- `POST /mcp`

Current tool surface:

- `list_appointments`
- `create_appointment`
- `update_appointment`
- `cancel_appointment`

Current auth shape:

- client access uses `Authorization: Bearer <token>` validated against the Worker secret `MCP_AUTH_TOKEN`
- the MCP Worker forwards to `edge-calsync` using the Worker secret `EDGE_INTERNAL_TOKEN`
- the live scheduling brain still remains on the origin and Apple CalDAV layer

Recommended operator setup:

1. Bootstrap or rotate an `mcp` token in the Pi runtime token store.
2. Set that value as the `MCP_AUTH_TOKEN` Worker secret.
3. Set the current `chatgpt` channel token as `EDGE_INTERNAL_TOKEN`.
4. Deploy the Worker.
5. Validate tool discovery and the full list/create/update/cancel flow against `POST /mcp`.

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
- `FindAvailabilityIntent`
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
- when account linking is configured, the Worker also checks the linked Alexa access token against the origin before it handles the voice request

Current readiness support:

- `GET /status` is intentionally public and returns a safe readiness summary only
- it exposes enabled-channel flags, token-hash presence flags, and Alexa allowlist readiness without revealing any secrets

Current scope:

- create an appointment through the shared scheduling brain
- create an appointment on a provider-aware named calendar target across Apple, Google, and Microsoft
- read appointments for a requested day
- read the next upcoming appointment in the next 30 days
- read back a few open availability windows for a requested date or date range
- cancel a matching appointment by title and date
- reschedule a matching appointment to a new day, time, or provider-aware named calendar target across Apple, Google, and Microsoft
- reject ambiguous calendar-name routing with a clear follow-up error instead of silently guessing across providers
- keep all actual calendar writes in the origin service
- rely on the origin's live Apple date-range sync so pre-existing family-calendar events can be surfaced to voice flows
- let the product preview real voice responses through `/alexa/simulate` before signed device requests are turned on

Operator setup:

1. Create or import the custom skill package from `workers/edge-calsync/alexa/skill-package`.
2. Configure Alexa account linking with:
   - authorization URL: `https://calsync.neonbutterfly.net/alexa/account-linking/authorize`
   - client ID: `calsync-alexa-household`
   - scopes: `calendar:read`, `calendar:write`
   - grant type: implicit
3. Save a household link code on `GET /alexa/setup` so the authorization page can finish the Alexa link safely.
4. After Alexa generates the real skill ID, set that ID in `ALEXA_ALLOWED_SKILL_IDS`.
5. Set `ENABLE_ALEXA=true`.
6. Redeploy the Worker.
7. Confirm the public policy URLs are reachable:
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

Recovery note:

- issue `#108`
- legacy Apple encrypted-secret recovery diagnostics now show on `/calendar/setup`, `/connections`, and shared readiness guidance whether the preserved Apple password is reusable with the current key or still needs the original key
- issue `#113`
- `/calendar/setup` now also accepts a one-time original CalSync encryption key so operators can recover a preserved Apple app-specific password from a legacy backup and re-save it under the current deployment key
- issue `#114`
- recovery-aware product messaging now points operators to enter that original key on Apple setup instead of implying the deployment key itself must be restored globally first
- issue `#115`
- once Apple is fully reconnected and writable again, `/connections` must stop rendering the stale `Recovered password / Needs original key` blocker card and instead prioritize the live connected Apple state
- issue `#116`
- once Apple is fully reconnected and writable again, shared readiness must point to the earliest real Alexa blockers like household account linking and Cloudflare Worker access instead of jumping straight to generic edge enablement
- issue `#117`
- once account linking is already configured, `GET /alexa/setup` should switch its Step 2.5 intro copy from first-time save guidance to configured-state guidance that explains the saved link code and authorization URL are already ready to use
- issue `#118`
- once account linking is already configured but the desired Alexa plan is still unsaved, shared readiness plus the Alexa next-action helper should point operators to save the Alexa plan and real skill ID before Cloudflare Worker apply-only guidance takes over
- issue `#119`
- the live Alexa setup and Connections forms should tell operators to copy the generated real Alexa skill ID from the Alexa developer console after importing the package, instead of making the `Allowed skill IDs` field read like unexplained raw config
- issue `#120`
- the remaining Alexa summaries on `/connections`, including the edge-route status card and the `Finish the live stack` Alexa line, should mirror that same desired-state-first guidance instead of falling back to older generic edge-enable wording
- issue `#121`
- `/alexa/setup` should keep the desired-settings and pending-edge cards truthful when no desired Alexa plan has been saved yet, instead of presenting the unsaved defaults like a real saved plan
- issue `#122`
- saving blank Alexa defaults or an enabled-without-skill-id state should not count as a real desired Alexa plan, so shared readiness and the Alexa setup or Connections cards must keep the real skill-ID step visible until at least one real skill ID is saved
- issue `#123`
- Alexa save responses should stop flashing `Desired Alexa settings saved securely.` when no real plan exists yet; blank or skill-ID-missing saves should stay local, skip edge apply attempts, and tell operators whether no plan was saved yet or a real skill ID is still required
- issue `#124`
- once the operator has only a skill-ID-missing Alexa draft, the helper copy under the Alexa forms should stop saying it will save a desired Alexa plan; it should instead say that the real Alexa skill ID is still required before CalSync can save a live plan or queue edge updates
- that same helper rule still applies after Cloudflare Worker access is already configured; the live GET forms should not fall back to `update the live edge Worker now` while the real skill ID is still missing
- issue `#125`
- once the operator has only an Alexa draft with `enable_alexa=true` and no real skill ID, the app should stop calling that state `defaults`; shared readiness and the Alexa desired-settings cards should treat it as an explicit draft-only state that is distinct from untouched defaults
- issue `#126`
- once the operator has only an Alexa draft with `enable_alexa=true` and no real skill ID, `/alexa/simulator` should stop reading like route enablement is the only missing step and should expose that the live Alexa plan is still only a draft
- issue `#127`
- once the operator has only an Alexa draft with no real skill ID saved yet, the `Live route` detail card on `GET /connections` should stop saying route enablement is the only missing step and should reuse the same blocker ordering as the other desired-state-first Alexa guidance on that page
- once Cloudflare Worker access is configured but Alexa is still only a draft with no real skill ID, the `Status` line in the `Edge Worker controls` panel on `GET /alexa/setup` should stop saying the Worker is ready to configure and should point at the real skill-ID blocker instead
- issue `#109`
- Alexa setup, the Connections Alexa panel, and the Alexa simulator now mirror that same legacy Apple encrypted-secret recovery state instead of falling back to fresh-password-only guidance
- issue `#110`
- blocked root workspace copy, booking blockers, stale appointment edit/cancel blockers, and appointment API recovery guidance now mirror that same legacy Apple encrypted-secret recovery state instead of falling back to fresh-password-only guidance
- issue `#107`
- the Alexa Worker code is now deployed live on Cloudflare with the recovery-guidance normalization, so launch, help, fallback, and recovery-error speech stay aligned with the original-key Apple recovery flow on the real edge path
- issue `#128`
- the Alexa docs and skill-package instructions now point operators to the current CalSync Alexa setup flow first, instead of reading like direct Worker env edits and redeploys are still the primary turn-on path
- issue `#129`
- the live Alexa Worker now defaults to deny when no allowed skill IDs are configured, so an empty allowlist cannot accidentally act permissive during draft or partially configured turn-on states

## Current follow-up item

The live edge path and product-managed Cloudflare access now work today. The real current Alexa follow-up item is the final live turn-on blocker:

- recover the real Alexa skill ID from the Alexa developer console
- save that skill ID through the CalSync Alexa setup flow so the desired Alexa plan can become a real saved plan instead of a draft
- enable the live Alexa route only after the real skill ID is present, then verify signed Alexa traffic or real device traffic end to end

Lower-priority ops nicety:

- a dedicated `CLOUDFLARE_API_TOKEN` in the Pi `.env` would still let `sync-cloudflare` run directly on-host without a workstation-assisted sync, but that is no longer the main blocker for Alexa turn-on
