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
- the first conversational app should expose create, edit, cancel, and date-range list flows

## Phase Notes

- issue `#32` builds on the preserved write-capable legacy work from earlier CalSync slices, now archived on `legacy/pre-chatgpt-brain-reset`
- the owned service is the durable contract; ChatGPT should never mutate CalDAV directly
- iCloud remains the family-facing calendar of record for day-to-day visibility
- CalSync should keep audit history and local event mappings so the later family workspace can grow without redesigning this slice

## Implemented In This Slice

- FastAPI runtime with `GET /`, `GET /healthz`, appointment mutation routes, and date-range lookup
- `GET /api/appointments` for date-range appointment lookup
- `GET /api/availability` for open-slot lookup
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

- the service requires a configured writable Apple calendar target before any mutation route can succeed
- the Apple account should use an app-specific password, not an interactive account password
- the service writes to one selected saved iCloud calendar target at a time, with one default target when the caller does not choose explicitly
- appointment changes should update the same Apple provider event rather than recreating a new one
- cancellations should delete the remote Apple event and mark the local record as `cancelled`

## Known Boundaries In Current Code

- no appointment search yet
- list is limited to explicit date windows, not free-form search
- no Google ingestion yet
- no iCloud Reminders sync yet
- no structured medical metadata API fields yet
- no ChatGPT Apps SDK wrapper yet; the Worker is the live edge, but the dedicated ChatGPT app layer is still future work

## In-Product Google OAuth Setup And Writable Targets Requirement

- GitHub issue: `#3`
- interpreted requirement: the product should support browser-based Google account connection and writable Google scheduling without forcing the operator to hand-edit host secrets or use a separate admin tool

Expected behavior:

- `GET /google/setup` should render an operator-facing Google setup page
- `POST /google/setup` should save the shared Google OAuth client ID and client secret
- those Google OAuth settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- `GET /auth/google/start` should begin a browser-based Google OAuth flow on the live CalSync domain
- `GET /auth/google/callback` should exchange the code, save the Google refresh token, and discover the available calendars
- the product should support more than one connected Google account under that shared OAuth app
- the product should expose a live refresh path so operators can resync one connected Google account and its discovered calendar catalog without reconnecting unnecessarily
- the product should expose a safe disconnect path that clears one linked Google account and its calendar list while preserving the shared deployment-wide OAuth client
- discovered Google calendars should appear as writable targets in the same create and edit flows used by the workspace
- the shared appointment service should be able to create, update, cancel, and date-range sync Google events through those targets

Behavioral boundary:

- this slice adds a shared Google write path inside the product, not a full Google-native standalone experience
- Apple remains the first family-facing target, but the scheduling brain should now treat connected Google calendars as first-class writable options

## In-Product Microsoft OAuth Setup And Writable Targets Requirement

- GitHub issue: `#49`
- interpreted requirement: the product should support browser-based Microsoft account connection and writable Outlook scheduling without forcing the operator to hand-edit host secrets or use a separate admin tool

Expected behavior:

- `GET /microsoft/setup` should render an operator-facing Microsoft setup page
- `POST /microsoft/setup` should save the shared Microsoft OAuth client ID and client secret
- those Microsoft OAuth settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- `GET /auth/microsoft/start` should begin a browser-based Microsoft OAuth flow on the live CalSync domain
- `GET /auth/microsoft/callback` should exchange the code, save the Microsoft refresh token, and discover the available calendars
- the product should support more than one connected Microsoft account under that shared OAuth app
- the product should expose a live refresh path so operators can resync one connected Microsoft account and its discovered calendar catalog without reconnecting unnecessarily
- the product should expose a safe disconnect path that clears one linked Microsoft account and its calendar list while preserving the shared deployment-wide OAuth client
- discovered Microsoft calendars should appear as writable targets in the same create and edit flows used by the workspace
- the shared appointment service should be able to create, update, cancel, and date-range sync Microsoft events through those targets

Behavioral boundary:

- this slice adds a shared Microsoft write path inside the product, not a full Outlook-native standalone experience
- Apple remains the first family-facing target, but the scheduling brain should now treat connected Microsoft calendars as first-class writable options beside Apple and Google

## First Scheduling UX Requirement

- GitHub issue: `#39`
- interpreted requirement: make the rebooted Apple-first backend usable through a clean family scheduling console instead of only API calls and future design notes

Expected UX behavior:

- `GET /` should render a polished scheduling console
- the root experience should let users create appointments directly into the Apple calendar through CalSync
- existing appointments should be visible, editable, and cancellable from the same console
- the UX should feel like a professional product surface, not a raw API debug page
- the web console should reuse the same appointment service and audit-backed write path as the API and Worker layers

## Scheduling Workspace Polish Requirement

- GitHub issue: `#40`
- interpreted requirement: turn the first scheduling console into a more professional scheduling workspace with clearer browsing, stronger appointment detail, and better product-level information architecture

Expected UX behavior:

- `GET /` should support day, week, and month schedule windows
- the workspace should show a selected appointment detail surface instead of only a flat list
- detail should explain where the appointment lives, when it changed, and what CalSync has done with it
- low-level provider metadata may still exist, but it should stay tucked behind a disclosure instead of dominating the primary experience
- the console should still use the same Apple write-back path for create, edit, and cancel

## Unified Connections UX Requirement

- GitHub issue: `#17`
- interpreted requirement: provider onboarding should feel like one professional product flow instead of a set of scattered setup pages

Expected behavior:

- `GET /connections` should summarize the live Apple and Google connection state in one place
- `GET /connections` should summarize the live Apple, Google, and Microsoft connection state in one place
- operators should be able to see which provider paths are already writable and which still need setup
- the shared workspace shell should link to that Connections surface directly
- Apple setup, Google setup, and Microsoft setup can remain separate deeper pages, but the day-to-day operator experience should have one clear entry point for connection state

## Connections Verification Center Requirement

- GitHub issue: `#52`
- interpreted requirement: the shared Connections surface should behave like a setup checklist and live verification center instead of only a read-only provider summary

Expected behavior:

- `GET /connections` should show a checklist-style view of Apple, Google, Microsoft, and Alexa readiness
- `POST /connections/test` should run the same in-product writable calendar smoke flow against a selected target from the Connections page
- the product should persist the last write proof for each writable target so operators can see whether a path was last verified or failed
- the Connections page should show the last write proof message and timestamp per target instead of relying on one-time flash messages only
- provider-specific setup pages may still expose `Run write test`, but `/connections` should become the calm operator surface where setup and verification come together

## Connections Provider Control Center Requirement

- GitHub issue: `#53`
- interpreted requirement: `/connections` should become the primary control surface for routine Google and Microsoft provider management instead of only a status-and-proof page

Expected behavior:

- `/connections` should expose direct connect actions for Google and Microsoft account onboarding
- `/connections` should expose direct refresh actions for one connected Google or Microsoft account at a time
- `/connections` should expose direct disconnect actions for one connected Google or Microsoft account at a time
- those actions should return to the shared Connections page with updated readiness and verification state instead of dropping the operator into a separate setup page
- the provider-specific setup pages can remain for deeper editing of shared OAuth app settings, but routine provider management should feel shared and product-like from `/connections`

## Planner-Style Schedule Board Requirement

- GitHub issue: `#54`
- interpreted requirement: the root schedule workspace should feel like a real planner product, so day, week, and month browsing must materially change the schedule presentation instead of only changing the query range under one agenda layout

Expected behavior:

- `/` should render a day board when `view=day`
- `/` should render a week board when `view=week`
- `/` should render a month board when `view=month`
- the selected-appointment detail pane and write actions should remain intact while the schedule board becomes more calendar-like
- the schedule board should remain useful even when some days are empty, so the planner surface still communicates open space instead of collapsing into a blank page

## Public Booking Page Requirement

- GitHub issue: `#55`
- interpreted requirement: CalSync should expose a first invitee-facing booking page so the shared write-capable scheduling brain is useful outside the internal operator workspace

Expected behavior:

- `GET /book` should render a public booking page
- the booking page should show open time from the same shared availability service used by the internal workspace
- an invitee should be able to choose one available time and submit a booking request
- the booking request should create a real appointment on the default writable connected calendar target
- the booking page should confirm the saved appointment details after success instead of bouncing the user into the internal operator workspace

## In-Product Booking Setup Requirement

- GitHub issue: `#56`
- interpreted requirement: operators should be able to control the invitee-facing booking experience from inside CalSync instead of leaving the public booking page hard-coded

Expected behavior:

- `GET /booking/setup` should render an operator-facing booking setup page
- the setup page should let operators save the public booking title, description, default duration, search window, success message, and writable target
- those booking settings should be stored securely in the product vault
- `GET /book` should render from those saved booking settings
- the public booking flow should use the configured writable target when it is still available

## Public Booking Availability Rules Requirement

- GitHub issue: `#57`
- interpreted requirement: the public booking page should behave like a real scheduling surface, so operators should be able to define which weekdays and hours are actually bookable

Expected behavior:

- `/booking/setup` should let operators choose the public booking weekdays
- `/booking/setup` should let operators choose the public booking day start and end times
- those public booking availability rules should be stored securely in the product vault
- `/book` should only show open slots that fall inside the saved public booking weekdays and daily time window
- the internal root workspace availability finder can keep its broader shared defaults; this slice only tightens the invitee-facing booking surface

## Multiple Public Booking Types Requirement

- GitHub issue: `#58`
- interpreted requirement: operators should be able to publish more than one public booking flow, each with its own shareable link and invitee-facing defaults, so CalSync feels like a real scheduling product instead of one global booking form

Expected behavior:

- `/booking/setup` should show the currently configured booking types
- operators should be able to create a named booking type with a stable slug
- each booking type should have a shareable public URL like `/book/school-intake`
- each booking type should carry its own public title, description, duration, search window, success message, writable target, and booking weekday/hour rules
- `/book` can continue to render the default booking type, but `/book/{slug}` should render the selected booking type directly

Expected API/edge support:

- `GET /api/appointments/{appointment_id}` should return the richer appointment detail payload
- `GET /v1/appointments/{appointment_id}` should expose the same detail through the Worker for future channel use

## Public Booking Catalog Requirement

- GitHub issue: `#59`
- interpreted requirement: once CalSync supports multiple public booking types, the root `/book` experience should feel like a professional scheduling catalog instead of silently dumping invitees into one default form

Expected behavior:

- when more than one public booking type exists, `GET /book` should render a chooser instead of a single booking form
- the chooser should explain that the invitee must pick the appointment flow that fits their need before choosing time
- each booking-type card should show the public title, description, duration, weekday summary, and time-window summary
- each booking-type card should link directly into its focused booking URL such as `/book/school-intake`
- when only one public booking type exists, `GET /book` may still render that focused booking form directly

## Public Booking Type Management Requirement

- GitHub issue: `#60`
- interpreted requirement: once CalSync supports multiple public booking types, operators should be able to manage those links directly from the product instead of needing backend-only cleanup or default switching

Expected behavior:

- `/booking/setup` should expose a direct action to make an existing booking type the default public `/book` flow
- `/booking/setup` should expose a direct action to delete an existing booking type
- when the current default booking type is deleted and another type remains, the product should promote a remaining type to default automatically
- deleting a booking type should remove its shareable `/book/{slug}` link cleanly
- the management actions should return the operator to `/booking/setup` with clear success or error feedback

## Apple Live Calendar Sync Requirement

- GitHub issue: `#41`
- interpreted requirement: the Apple-first workspace and Alexa flows must read the actual household Apple calendar, not only CalSync-created rows

Expected behavior:

- date-range schedule views should sync existing Apple calendar events into the shared appointment store before rendering
- `GET /api/appointments` should surface Apple events that already existed before CalSync created anything
- default active views should hide cancelled appointments so stale noise does not dominate the schedule or voice responses
- cancelled items should still remain available for explicit reference when the operator intentionally asks for them
- edit and cancel flows should work for provider-synced Apple events, not just locally originated writes
- Alexa day-list, cancel, and reschedule flows should benefit from the same synced Apple event inventory because they already call the shared origin APIs

Operational boundary:

- this first live-read slice only needs range-based Apple sync for the requested window
- it does not yet need a full long-running background mirror of the entire calendar history

## In-Product Apple Calendar Setup Requirement

- GitHub issue: `#46`
- interpreted requirement: the Apple-first product should manage its own Apple calendar connection from the UI instead of depending only on host `.env` edits

Expected behavior:

- `GET /calendar/setup` should render an operator-facing Apple calendar setup page
- `POST /calendar/setup` should save the Apple account label, Apple username, Apple app-specific password, primary calendar URL, and primary calendar name
- the product should support more than one connected Apple account under that setup surface
- those product-managed Apple settings should be stored encrypted at rest with `ENCRYPTION_KEY`
- the appointment service and readiness surface should fall back to product-vault Apple settings when deployment env values are absent
- the main workspace and Alexa setup flow should link back to the Apple calendar setup page

## Multi-Calendar Apple Target Requirement

- GitHub issue: `#31`
- interpreted requirement: the Apple-first product should support more than one saved writable Apple calendar target, not only one hard-wired family destination

Expected behavior:

- `POST /calendar/setup/calendars` should let the operator add another Apple calendar target for a selected Apple account without losing the current default target
- create and edit flows should expose a target calendar picker when more than one Apple calendar is saved
- `POST /api/appointments` should accept `target_calendar_url` so callers can choose a non-default Apple destination
- `PATCH /api/appointments/{appointment_id}` should accept `target_calendar_url` so the appointment can move between saved Apple calendars
- date-range sync should read across the saved Apple calendar targets instead of only one primary calendar

## Named Apple Calendar Voice Target Requirement

- GitHub issue: `#47`
- interpreted requirement: Alexa and the in-product simulator should be able to target a saved Apple calendar by human-friendly name instead of always assuming the default destination

Expected behavior:

- the shared scheduling contract should accept `target_calendar_name` in create and update flows
- Alexa create flows should support a calendar-name slot for choosing a saved Apple target
- Alexa reschedule flows should support a new calendar-name slot for moving an appointment to another saved Apple target
- the in-product simulator should expose those calendar-name fields so voice routing can be tested without guessing raw payloads

## Provider-Aware Alexa Calendar Target Requirement

- GitHub issue: `#50`
- interpreted requirement: Alexa and the in-product simulator should treat Apple, Google, and Microsoft calendar targets as one provider-aware scheduling surface instead of staying Apple-shaped after the shared scheduling brain became multi-provider

Expected behavior:

- the simulator should populate calendar-name options from the shared scheduling brain, not from Apple-only runtime state
- `target_calendar_name` should resolve against a unified provider-aware calendar target catalog
- provider-aware names such as `Family on Google` or `Calendar on Microsoft` should route correctly
- ambiguous bare names should fail clearly with actionable options instead of silently falling through between providers
- voice-facing docs and setup guidance should describe provider-aware targeting across Apple, Google, and Microsoft

## In-Product Writable Calendar Smoke Test Requirement

- GitHub issue: `#51`
- interpreted requirement: the product should let operators prove a writable Apple, Google, or Microsoft calendar target actually supports create, update, and cancel from inside CalSync

Expected behavior:

- Apple, Google, and Microsoft writable target cards should expose a `Run write test` action
- the shared scheduling brain should run a safe create -> update -> cancel verification cycle against the selected target
- if a step fails after create, CalSync should attempt cleanup and surface the real error
- the product should show a clear success message naming the calendar and provider that passed

## Availability Requirement

- GitHub issue: `#48`
- interpreted requirement: the Apple-first product should suggest open windows from the shared schedule through the workspace, edge API, and Alexa instead of only listing appointments

Expected behavior:

- `GET /api/availability` should return open windows for a requested date range and duration
- `GET /v1/availability` should expose the same behavior through the edge Worker
- the root workspace should expose a simple availability finder
- Alexa should support a `FindAvailabilityIntent`
- the simulator should expose the same intent so the running product can preview availability speech

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
- the API container must mount that same host `.runtime` directory so readiness and origin-side channel tooling reflect the real source-of-truth

## Remote MCP Worker Requirement

- GitHub issue: `#37`
- interpreted requirement: expose the Apple-first scheduling brain as a real authenticated remote MCP server instead of only a raw edge HTTP API

Expected behavior:

- deploy a dedicated MCP Worker on `https://mcp-calsync.neonbutterfly.net/mcp`
- keep a `workers.dev` endpoint available until the custom hostname is delegated cleanly
- expose:
  - `list_appointments`
  - `create_appointment`
  - `update_appointment`
  - `cancel_appointment`
- require authenticated client access from day one
- keep the edge Worker and origin as the only places that know the lower-level scheduling API and Apple write path
- forward MCP tool calls into the live edge/origin stack instead of duplicating calendar logic

## Alexa Skill Requirement

- GitHub issue: `#38`
- interpreted requirement: add a first Alexa custom-skill layer on top of the same shared scheduling brain instead of creating a separate voice-only backend

Expected voice behavior:

- Alexa should use the same appointment create, list, cancel, and reschedule flows as other channels
- the first voice slice should support:
  - launch and help
  - create appointment
  - list appointments for a requested day
  - read the next upcoming appointment
  - cancel a matching appointment
  - reschedule a matching appointment
- all actual calendar mutation must still happen in the origin service

Expected auth shape:

- the Alexa route should verify signed Alexa web-service requests using Amazon's certificate and request-signature flow
- the Worker should only accept configured Alexa skill IDs from `ALEXA_ALLOWED_SKILL_IDS`
- the route should remain disabled until `ENABLE_ALEXA=true`

Current repo artifacts:

- Worker route: `POST /alexa`
- Worker simulator route: `POST /alexa/simulate`
- interaction model: `workers/edge-calsync/alexa/interaction-model.json`
- importable skill package: `workers/edge-calsync/alexa/skill-package`
- voice adapter implementation: `workers/edge-calsync/src/alexa.ts`
- origin-side simulator page:
  - `GET /alexa/simulator`
  - `POST /alexa/simulator`
- public policy pages on the origin:
  - `GET /privacy`
  - `GET /terms`

Known boundary in this slice:

- this is a first shared-household Alexa adapter, not a full multi-user account-linking platform
- before the skill is fully live, the product should still preview the real voice logic through an authenticated simulator path instead of repo-only tests or blind guesswork

## Full-Stack Readiness Requirement

- GitHub issue: `#43`
- interpreted requirement: the product itself should explain whether the Apple-first origin, channel tokens, edge Worker, and Alexa setup are actually ready, instead of forcing operators to infer readiness from docs or deployment memory

Expected behavior:

- `GET /api/readiness` should return a safe merged readiness snapshot
- the root scheduling workspace should surface that snapshot in plain language
- `GET /status` on the edge Worker should return public-safe channel and Alexa readiness without requiring auth
- the readiness surface should never expose raw tokens, secrets, or skill IDs
- the app should point to the next meaningful operator action when Alexa or channel setup is incomplete

## In-Product Alexa Setup Requirement

- GitHub issue: `#45`
- interpreted requirement: the running product should help operators finish Alexa setup directly, including a downloadable skill package and the live endpoint/policy links

Expected behavior:

- `GET /alexa/setup` should render a voice setup page inside the product
- `GET /alexa/skill-package.zip` should return the Alexa custom skill package from the running app
- the setup page should show the live edge endpoint, privacy URL, terms URL, and current readiness state
- the setup page should let the operator save Cloudflare Worker-management credentials inside the product instead of relying only on host `.env` edits
- those product-managed Worker credentials should be stored encrypted at rest with `ENCRYPTION_KEY`
- the setup page should read the current edge Worker Alexa flags when Cloudflare worker-management settings are available
- the setup page should let the operator update `ENABLE_ALEXA` and `ALEXA_ALLOWED_SKILL_IDS` from the product when the Cloudflare token has `Workers Scripts Write`
- the root scheduling workspace should link operators into the Alexa setup flow
