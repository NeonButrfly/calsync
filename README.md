# CalSync

CalSync is being rebooted as a conversational scheduling system with Apple-first roots and growing Google and Microsoft write paths.

The previous full CalSync application was preserved on the `legacy/pre-chatgpt-brain-reset` branch so we can still reference its provider work, write-back patterns, and earlier UI ideas without carrying that whole surface forward on `main`.

## Current focus

- ChatGPT app for household calendars
- small owned service as the scheduling brain
- iCloud as the first family-facing calendar target
- in-product Google OAuth connect plus writable Google targets
- in-product Microsoft OAuth connect plus writable Outlook targets
- future expansion toward iCloud Reminders sync and richer family/medical appointment logic

## Working docs

- Design spec: [docs/superpowers/specs/2026-05-27-calsync-apple-calendar-chatgpt-app-design.md](docs/superpowers/specs/2026-05-27-calsync-apple-calendar-chatgpt-app-design.md)
- Cloudflare edge Worker design: [docs/superpowers/specs/2026-05-28-calsync-cloudflare-edge-worker-chatgpt-design.md](docs/superpowers/specs/2026-05-28-calsync-cloudflare-edge-worker-chatgpt-design.md)
- Reset plan: [docs/superpowers/plans/2026-05-27-calsync-legacy-archive-reset.md](docs/superpowers/plans/2026-05-27-calsync-legacy-archive-reset.md)
- Apple-first service plan: [docs/superpowers/plans/2026-05-28-calsync-apple-first-service-kayraspi-deploy.md](docs/superpowers/plans/2026-05-28-calsync-apple-first-service-kayraspi-deploy.md)
- Operations guide: [docs/ops.md](docs/ops.md)
- Cloudflare fit and bootstrap: [docs/cloudflare.md](docs/cloudflare.md)

## Current service slice

Issues `#3`, `#17`, `#31`, `#32`, `#36`, `#37`, `#38`, `#39`, `#40`, `#41`, `#43`, `#45`, `#46`, `#47`, `#48`, `#49`, `#50`, `#51`, `#52`, `#53`, `#54`, `#55`, `#56`, `#57`, `#58`, `#59`, `#60`, `#61`, `#62`, `#63`, `#64`, `#65`, `#66`, `#67`, `#68`, `#69`, and `#70` are now backed by:

- FastAPI runtime on port `3080`
- Postgres-backed local appointment storage
- Alembic migrations
- Apple CalDAV adapter for create, update, cancel, and range-based event sync
- a polished scheduling workspace at `/` for create, edit, cancel, filtered browsing, and appointment detail review
- a planner-style scheduling board at `/` that now renders distinct day, week, and month planning states instead of only one stacked agenda layout
- a first public booking page at `/book` that lets an invitee claim an open time and create a real appointment through the same shared scheduling brain
- invitee contact capture in the public booking flow, so `/book` stores who requested the time and how to reach them in the resulting appointment context
- an in-product booking setup page at `/booking/setup` that lets operators control the public booking title, description, duration defaults, search window, success copy, and target calendar
- public booking availability rules that let operators choose the invitee-facing bookable weekdays and daily booking hours instead of relying on one hard-coded slot window
- multiple public booking types with shareable links such as `/book/school-intake`, so different appointment flows can carry their own copy, duration, and availability defaults
- a public booking catalog at `/book` that can now present multiple booking types cleanly before invitees drill into a specific `/book/{slug}` flow
- in-product booking type management actions so operators can now make one type the default `/book` flow or delete a stale public link without touching backend state
- a dedicated connections workspace at `/connections` that summarizes Apple, Google, and Microsoft setup in one product surface
- a checklist-style connections workspace at `/connections` that also shows persisted write verification and direct run-test actions
- a stronger Connections control center that can also trigger shared Google and Microsoft connect, refresh, and disconnect actions without leaving the page
- Alexa turn-on controls in `/connections`, so the shared operator surface now shows live-vs-desired voice state and can save or apply edge settings without leaving the control center
- encrypted operator-settings backup and restore from `/connections`, so Apple, Google, Microsoft, Alexa, and booking setup can be exported and recovered without hand-rebuilding the product vault
- Local audit entries and appointment-to-provider event mapping
- A dedicated Cloudflare Worker in `workers/edge-calsync`
- Live ChatGPT-first edge hostname: `https://edge-calsync.neonbutterfly.net`
- a dedicated remote MCP Worker in `workers/mcp-calsync`
- live MCP hostname: `https://mcp-calsync.neonbutterfly.net`
- workers.dev MCP fallback: `https://mcp-calsync.kaymayers9.workers.dev`
- Live Pi origin hostname: `https://calsync.neonbutterfly.net`
- a first Alexa custom-skill adapter on top of the same shared scheduling brain
- named Apple calendar targeting through Alexa and the simulator, so voice flows can choose a saved household calendar instead of always using the default destination
- provider-aware Alexa calendar targeting across Apple, Google, and Microsoft, so voice and simulator flows can choose the right connected calendar path without relying on Apple-only assumptions
- live Apple primary-calendar reads, so existing household events show up in the shared workspace and voice flows
- multiple saved Apple calendar targets, so create, edit, and sync flows can work across more than one household calendar
- a product-facing readiness surface for Apple setup, channel tokens, edge reachability, and Alexa status
- an in-product Apple calendar setup page plus encrypted product-vault storage for the Apple read/write connection
- multiple connected Apple accounts under the same product-managed scheduling surface, with writable targets from each account available to the shared scheduling brain
- an in-product Google setup page plus encrypted product-vault storage for the shared Google OAuth app and connected-account refresh token
- browser-based Google OAuth connect on the live CalSync domain
- in-product Google calendar refresh and disconnect controls so operators can resync calendar discovery or safely clear one connected Google account without losing the shared OAuth app
- multiple connected Google accounts under one shared OAuth app, with calendars from each account available to the same create, edit, cancel, and schedule lookup flows
- writable Google calendar targets that share the same create, edit, cancel, and schedule lookup paths
- an in-product Microsoft setup page plus encrypted product-vault storage for the shared Microsoft OAuth app and connected-account refresh token
- browser-based Microsoft OAuth connect on the live CalSync domain
- in-product Microsoft calendar refresh and disconnect controls so operators can resync one connected Microsoft account or safely clear it without losing the shared OAuth app
- multiple connected Microsoft accounts under one shared OAuth app, with calendars from each account available to the same create, edit, cancel, and schedule lookup flows
- writable Microsoft calendar targets that share the same create, edit, cancel, and schedule lookup paths
- in-product writable calendar smoke tests, so Apple, Google, and Microsoft targets can verify create, update, and cancel from inside CalSync
- persisted connection verification summaries, so `/connections` can show the last successful or failed write proof per writable calendar target
- an in-product Alexa setup page plus downloadable skill package
- an encrypted product vault for Cloudflare Worker-management credentials, so the Alexa setup flow can store operator access safely inside CalSync
- persisted desired Alexa edge settings plus live-vs-desired drift visibility, so operators can save the intended skill allowlist and enablement plan even before Cloudflare Worker management is available
- voice-specific next guidance on Alexa-focused setup surfaces, so the Alexa setup page and Connections voice panel explain the actual voice turn-on work instead of falling back to generic provider onboarding copy
- a simulator readiness summary for no-calendar voice testing states, so `/alexa/simulator` explains when LaunchRequest is still useful and why scheduling-intent tests are still blocked
- a first availability finder across the workspace, edge API, and Alexa so CalSync can suggest open appointment windows instead of only listing busy ones

### Endpoints

- `GET /`
- `GET /booking/setup`
- `POST /booking/setup/types/default`
- `POST /booking/setup/types/delete`
- `GET /connections`
- `GET /connections/settings-backup`
- `GET /book`
- `POST /connections/test`
- `POST /connections/alexa`
- `POST /connections/settings-restore`
- `POST /connections/google/refresh`
- `POST /connections/google/disconnect`
- `POST /connections/microsoft/refresh`
- `POST /connections/microsoft/disconnect`
- `GET /calendar/setup`
- `POST /calendar/setup`
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
- `GET /api/info`
- `GET /healthz`
- `GET /api/readiness`
- `POST /api/alexa/account-linking/validate`
- `GET /api/appointments`
- `GET /api/appointments/{appointment_id}`
- `GET /api/availability`
- `POST /api/appointments`
- `PATCH /api/appointments/{appointment_id}`
- `POST /api/appointments/{appointment_id}/cancel`

### Web console

The root page now acts as the first family scheduling UX:

- polished create-appointment form
- target-calendar picker for create and edit flows across saved Apple and connected Google or Microsoft calendars
- day, week, and month schedule browsing
- real Apple and connected Google or Microsoft calendar events synced into the local scheduling brain for the requested window
- active schedule views hide cancelled appointments by default while still allowing a reference view when you explicitly show them
- selected appointment detail with audit trail and provider metadata
- edit flow for existing appointments
- cancel flow for existing appointments
- an open-time finder for 30 and 60 minute style schedule gaps
- direct Apple, Google, and Microsoft calendar read/write through the same backend used by the API and Worker
- a first in-product readiness panel that explains whether Apple, tokens, edge, and Alexa are actually ready
- a first in-product Apple calendar setup page that stores Apple credentials and calendar details securely in the product vault
- a first in-product Apple account management flow that can store more than one Apple account and add writable targets per account
- a first in-product Google setup page that stores the shared OAuth app securely and supports browser-based Google connect
- a first in-product Google account management flow that can connect more than one Google account, refresh discovered calendars per account, and disconnect one account without losing the saved OAuth client
- a first in-product Microsoft setup page that stores the shared OAuth app securely and supports browser-based Microsoft connect
- a first in-product Microsoft account management flow that can connect more than one Microsoft account, refresh discovered calendars per account, and disconnect one account without losing the saved OAuth client
- a first in-product write-test action on Apple, Google, and Microsoft target cards so operators can prove a writable calendar path works end to end
- a first in-product Connections page that pulls Apple, Google, and Microsoft readiness into one calmer operator view
- that Connections workspace now also acts as a checklist and verification center with persisted last-write proof per target
- that Connections workspace now also acts as the primary day-to-day provider control surface for Google and Microsoft account actions
- that Connections workspace now also surfaces the Alexa last-mile launch state, desired-vs-live drift, and a quick apply form for edge settings
- the main schedule workspace now adapts the planner board for day, week, and month browsing so the selected horizon changes the visual planning surface instead of only the query range
- the workspace capability summary now reflects the actual connected readiness state, so Apple, Google, Microsoft, and Alexa copy stays truthful while setup is still in progress
- the root workspace now also blocks the create flow clearly when no writable calendar is connected, so operators get direct setup guidance instead of an apparently live scheduling form
- the root workspace now also blocks availability search clearly when no writable calendar is connected, so operators do not get fake “no openings” signals from an unconfigured scheduling path
- the root workspace now also blocks the empty schedule board and detail panel clearly when no writable calendar is connected, so an unconfigured runtime does not masquerade as a normal empty calendar
- a first public booking page that uses the same availability search and writable appointment path as the internal workspace
- that public booking flow is now configurable from `/booking/setup`, including invitee-facing copy, default duration, search horizon, success message, and the writable target used for new bookings
- that public booking flow now also respects operator-managed booking weekdays plus daily start and end hours
- that public booking flow now also blocks the invitee-facing availability refresh controls clearly when no writable calendar is connected, so the page does not look half-live during provider setup
- that booking setup flow now supports multiple named booking types, each with its own public slug and shareable invitee-facing URL
- that default `/book` route now becomes a booking-type chooser when multiple public booking types exist, while keeping direct `/book/{slug}` links for focused flows
- that booking setup flow now also lets operators make an existing booking type the default public flow or delete a stale type directly from the UI
- that public booking flow now captures the requester name and contact details so operators can follow up without losing that context after the appointment is created
- a first in-product Alexa setup page that links the live endpoint, policy URLs, and skill package download
- a first in-product Cloudflare access form that stores Worker-management credentials securely in the product vault
- a first in-product Alexa edge-settings form that can always save the desired Alexa state in the product vault, then apply Worker Alexa flags live when Cloudflare worker-management permission is configured
- a first in-product Alexa simulator page that previews real voice responses before the final Amazon console turn-on

### Worker routes

- `GET /status`
- `GET /v1/appointments`
- `GET /v1/appointments/{appointment_id}`
- `GET /v1/availability`
- `POST /v1/appointments`
- `PATCH /v1/appointments/{appointment_id}`
- `POST /v1/appointments/{appointment_id}/cancel`
- `POST /alexa`
- `POST /alexa/simulate`

### MCP routes

- `POST /mcp`

### MCP tool slice

The first remote MCP server now lives beside the edge Worker:

- primary custom domain endpoint: `https://mcp-calsync.neonbutterfly.net/mcp`
- workers.dev fallback endpoint: `https://mcp-calsync.kaymayers9.workers.dev/mcp`
- project: `workers/mcp-calsync`
- tools:
  - `list_appointments`
  - `create_appointment`
  - `update_appointment`
  - `cancel_appointment`

Current MCP auth shape:

- client access requires `Authorization: Bearer <token>` matching `MCP_AUTH_TOKEN`
- the MCP Worker forwards internally to `edge-calsync` using `EDGE_INTERNAL_TOKEN`
- the edge/origin scheduling brain remains the only place where calendar mutations actually happen

### Alexa skill slice

The first Alexa integration now lives beside the Worker:

- Worker voice route: `POST /alexa`
- interaction model: `workers/edge-calsync/alexa/interaction-model.json`
- importable skill package: `workers/edge-calsync/alexa/skill-package`
- in-product setup page: `GET /alexa/setup`
- in-product edge-settings update: `POST /alexa/setup`
- in-product simulator page: `GET /alexa/simulator`
- in-product package download: `GET /alexa/skill-package.zip`
- first intents:
  - `CreateAppointmentIntent`
  - `ListAppointmentsIntent`
  - `FindAvailabilityIntent`
  - `CancelAppointmentIntent`
  - `RescheduleAppointmentIntent`
  - `AMAZON.HelpIntent`
  - `AMAZON.CancelIntent`
  - `AMAZON.StopIntent`
  - `AMAZON.FallbackIntent`

Current voice capabilities:

- create a new appointment
- create a new appointment on a provider-aware named calendar target across Apple, Google, and Microsoft
- read appointments for a requested day
- read the next upcoming appointment in the next 30 days
- read back open appointment windows for a requested date or date range
- cancel a matching appointment by title and date
- reschedule a matching appointment to a new day, time, or provider-aware named calendar target across Apple, Google, and Microsoft
- act on Apple events that already existed in the family calendar once the origin has synced the requested date window
- share the same open-time lookup and writable scheduling brain that now supports connected Google targets too

Current auth shape:

- the Worker verifies incoming Alexa web-service requests using the Amazon certificate and request-signature flow
- the Worker also checks the configured Alexa skill ID allowlist in `ALEXA_ALLOWED_SKILL_IDS`
- the voice route stays disabled until `ENABLE_ALEXA=true`
- the setup flow now also supports first-household Alexa account linking through a saved link code plus a CalSync-hosted implicit-grant authorization page at `/alexa/account-linking/authorize`
- the live Worker now checks that linked Alexa access token before handling signed voice requests when account linking is configured
- public policy pages for the skill package now live at:
  - `https://calsync.neonbutterfly.net/privacy`
  - `https://calsync.neonbutterfly.net/terms`
- an authenticated simulator route now exists on the Worker so the product can preview the real voice responses before the skill is fully live
- the setup page can now save Cloudflare Worker-management credentials in the product vault, encrypted at rest with `ENCRYPTION_KEY`
- the setup page can now read and update `ENABLE_ALEXA` plus `ALEXA_ALLOWED_SKILL_IDS` on the edge Worker when the configured Cloudflare API token has `Workers Scripts Write`

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
  "attendees_text": "Mom, Kayra",
  "target_calendar_url": "https://caldav.icloud.com/family/"
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

The API container now mounts that same `.runtime` directory at `/app/.runtime`, so product readiness and any origin-side channel tooling read the same live token source-of-truth.

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
4. Optionally override the display timezone used for synced provider events:
   - `DEFAULT_TIMEZONE`
5. Choose a real `ENCRYPTION_KEY` so product-vault secrets are encrypted safely at rest.
6. If you want Google scheduling through the in-product browser connect flow, save the shared Google OAuth app on `GET /google/setup`.
7. If you want Pi-driven Cloudflare KV sync from the app runtime, also fill in:
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_TOKEN_KV_NAMESPACE_ID`
   - `EDGE_BASE_URL`
8. Start the stack with Docker Compose.
9. Verify `http://127.0.0.1:3080/healthz`.
10. Open `http://127.0.0.1:3080/` for the scheduling console.
11. If you are preparing the Alexa slice, also set:
  - `ALEXA_ALLOWED_SKILL_IDS`
  - `ALEXA_DEFAULT_TIMEZONE`

The API will not create calendar events until the Apple settings are populated.

If you do not want Apple calendar credentials to live only in host env, the product now exposes `GET /calendar/setup`. That page stores the Apple username, app-specific password, primary calendar URL, calendar name, and account label securely in the product vault, encrypted at rest with `ENCRYPTION_KEY`.

That same setup surface now also supports more than one Apple account plus `POST /calendar/setup/calendars`, which lets operators add more Apple calendar targets per account and choose which one should be the default destination for new appointments.

If you want Google scheduling without host-only secret edits, the product now exposes `GET /google/setup`. That page stores the shared Google OAuth client ID and secret securely in the product vault, then uses `GET /auth/google/start` and `GET /auth/google/callback` for the browser-based connect flow. Once connected, CalSync saves the Google refresh token, discovers calendars, and surfaces those writable Google targets in the same target-calendar picker used by the workspace. The same page can now manage multiple connected Google accounts under that one shared OAuth app, refresh calendar discovery per account, and disconnect one account while leaving the shared OAuth app in place.

If you want Outlook scheduling without host-only secret edits, the product now exposes `GET /microsoft/setup`. That page stores the shared Microsoft OAuth client ID and secret securely in the product vault, then uses `GET /auth/microsoft/start` and `GET /auth/microsoft/callback` for the browser-based connect flow. Once connected, CalSync saves the Microsoft refresh token, discovers calendars, and surfaces those writable Microsoft targets in the same target-calendar picker used by the workspace. The same page can now manage multiple connected Microsoft accounts under that one shared OAuth app, refresh calendar discovery per account, and disconnect one account while leaving the shared OAuth app in place.

If you prefer not to keep a Worker-management API token in the host `.env`, the Alexa setup page can now save the Cloudflare account ID and API token inside CalSync. The product vault encrypts those values at rest with `ENCRYPTION_KEY`, then uses them for live `ENABLE_ALEXA` and `ALEXA_ALLOWED_SKILL_IDS` management.

That same Alexa setup flow now also persists the desired `ENABLE_ALEXA` and `ALEXA_ALLOWED_SKILL_IDS` state inside the product vault, then shows whether the live Worker still differs from that saved plan. This lets operators save the intended Alexa turn-on state even when Cloudflare Worker management is not configured yet.

## Tracking

- Conversational Apple-first app slice: issue `#32`
- Cloudflare edge Worker slice: issue `#36`
- Remote MCP server slice: issue `#37`
- Alexa skill slice: issue `#38`
- In-product Alexa setup flow: issue `#45`
- In-product Apple calendar setup vault: issue `#46`
- In-product Google OAuth setup and writable targets: issue `#3`
- In-product Microsoft OAuth setup and writable targets: issue `#49`
- Multi-calendar Apple writable targets and sync: issue `#31`
- Named Apple calendar targeting for Alexa and simulator: issue `#47`
- Availability search across workspace, edge, and Alexa: issue `#48`
- Runtime token store mount fix: issue `#44`
- Provider-aware Alexa calendar targeting across Apple, Google, and Microsoft: issue `#50`
- In-product writable calendar smoke tests: issue `#51`
- In-product public booking setup: issue `#56`
- Public booking availability rules: issue `#57`
- Multiple public booking types with shareable links: issue `#58`
- Public booking catalog for multiple appointment types: issue `#59`
- In-product booking type management actions: issue `#60`
- Persist desired Alexa edge settings and drift visibility: issue `#61`
- Fix workspace planner copy regression and live capability messaging: issue `#62`
- First family scheduling UX: issue `#39`
- Scheduling workspace polish: issue `#40`
- Apple live calendar sync into the shared workspace and Alexa: issue `#41`
- Full-stack readiness and Alexa status surface: issue `#43`
- Legacy archive and clean reset: issue `#33`

## Legacy archive

If we need anything from the old system, use the `legacy/pre-chatgpt-brain-reset` branch as the source of truth for that implementation history.
