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

Issues `#3`, `#17`, `#31`, `#32`, `#36`, `#37`, `#38`, `#39`, `#40`, `#41`, `#43`, `#45`, `#46`, `#47`, `#48`, `#49`, `#50`, `#51`, `#52`, `#53`, `#54`, `#55`, `#56`, `#57`, `#58`, `#59`, `#60`, `#61`, `#62`, `#63`, `#64`, `#65`, `#66`, `#67`, `#68`, `#69`, `#70`, `#71`, `#72`, `#73`, `#76`, `#77`, `#78`, `#79`, `#80`, `#81`, `#82`, `#83`, `#84`, `#85`, `#86`, `#87`, `#88`, `#89`, `#90`, `#91`, `#92`, `#93`, `#94`, `#95`, `#96`, `#97`, `#98`, `#99`, `#100`, `#101`, `#102`, `#103`, `#104`, `#105`, and `#106` are now backed by:

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
- recovery-aware Apple reconnect actions on `/` and `/booking/setup`, so blocked operator surfaces now point straight at the loaded Apple recovery path instead of only saying a writable calendar is missing
- recovery-aware Apple reconnect messaging across the blocked root workspace panels, so schedule, detail, create, and availability states all point at the same real reconnect path
- recovery-aware Apple reconnect guidance on Alexa setup and Connections, so the voice turn-on flow now follows the real recovered-calendar prerequisite instead of generic no-calendar wording
- recovery-aware Apple reconnect guidance through the full booking-setup operator flow, so the target-behavior card and blocked save/create responses now match the top-level booking blocker
- recovery-aware Apple reconnect guidance in the root workspace capability summary, so the `What works today` list now matches the real recovered-calendar reconnect state instead of falling back to blank-install wording
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
- truthful save-only Alexa action labels on `/alexa/setup` and `/connections`, so those surfaces stop implying a live Worker apply when Cloudflare Worker management is still unavailable
- restore-aware readiness guidance, so recovery-shaped deployments with only non-provider settings left now point operators toward encrypted restore from `/connections` instead of acting like fresh provider onboarding is the only next move
- a legacy Pi-backup import path for Apple recovery hints, so the preserved SQL backup can surface the old iCloud account and calendar URLs inside CalSync instead of forcing manual dump inspection
- one-step loading of recovered Apple backup hints into the setup form, so operators can start from the imported account and calendar values and only add a fresh app-specific password
- automatic loading of the recommended recovered Apple hint on the default setup page, so recovery mode opens straight into the real Family reconnect path instead of waiting for an extra click
- shared Apple recovery guidance that now reflects the already-loaded reconnect state, so readiness and Connections stop telling operators to perform a manual hint-load step that is no longer needed
- recovery-aware Apple messaging across readiness, Connections, and Apple setup, so the live product points directly at the reconnect step once legacy hints have been imported
- a safe Apple setup validation step before reconnect save, so operators can test a fresh Apple username, password, and calendar URL without persisting bad credentials first
- legacy Apple recovery hint ranking that now prefers the real recovered writable booking target over a merely enabled personal-reference calendar
- a fully blocked disconnected root workspace, so stale hero counts, next-up copy, and selected appointment detail no longer appear when no writable calendar is connected
- voice-specific next guidance on Alexa-focused setup surfaces, so the Alexa setup page and Connections voice panel explain the actual voice turn-on work instead of falling back to generic provider onboarding copy
- shared Alexa account-linking readiness on `/connections`, so the last-mile voice panel now shows whether the household link code is configured instead of treating Cloudflare and skill IDs as the only remaining setup state
- an account-linking row in Alexa Step 4, so the final live turn-on summary shows that prerequisite directly instead of hiding it earlier in the page
- a writable-calendar row in Alexa Step 4, so the final live turn-on summary now shows the first real scheduling prerequisite instead of leaving it only in the next-action sentence
- a Cloudflare-access row in Alexa Step 4, so the final live turn-on summary now shows whether product-managed Worker access is configured instead of hiding that blocker only in helper text
- a desired-settings row in Alexa Step 4, so the final live turn-on summary now shows whether CalSync actually has a saved Alexa plan instead of leaving that prerequisite only in a separate status card
- a truthful desired-settings card on `/connections`, so the shared Alexa panel now says when no Alexa plan has been saved yet instead of presenting unsaved defaults like a real live plan
- a writable-calendar card on `/connections` for Alexa, so the shared voice panel now surfaces the first real scheduling prerequisite instead of hiding it only in next-action copy
- a truthful live-route card on `/connections` for Alexa, so the shared voice panel no longer acts like route enablement is the only missing step when the real skill ID or Cloudflare access still comes first
- truthful Google and Microsoft next-action summaries on `/connections`, so the shared finish-line panel now says to save the shared OAuth app first when browser connect is not actually available yet
- a simulator readiness summary for no-calendar voice testing states, so `/alexa/simulator` explains when LaunchRequest is still useful and why scheduling-intent tests are still blocked
- recovery-aware simulator readiness guidance on `/alexa/simulator`, so the voice testing page now points operators to Apple reconnect instead of falling back to blank-install no-calendar wording when legacy hints already exist
- recovery-aware Alexa simulator selector guidance on `/alexa/simulator`, so empty target-calendar and reschedule-calendar helper text now points to Apple reconnect instead of blank-install setup wording when legacy hints already exist
- recovery-aware public booking guidance on `/book`, so blocked invitee-facing booking states now point to Apple reconnect instead of blank-install no-calendar wording when legacy hints already exist
- recovery-aware public booking submit errors, so blocked direct booking requests now point to Apple reconnect instead of a stale generic no-target error when legacy hints already exist
- recovery-aware root appointment submit errors, so blocked direct schedule-workspace create requests now point to Apple reconnect instead of a raw Apple config error when legacy hints already exist
- recovery-aware Alexa scheduling errors, so blocked simulator and voice scheduling intents now point to Apple reconnect instead of speaking a raw Apple config error when legacy hints already exist
- recovery-aware Alexa read intents, so blocked simulator and voice list, next, availability, cancel, and reschedule flows no longer leak stale local appointments or generic search fallbacks when Apple reconnect is still the real blocker
- a first availability finder across the workspace, edge API, and Alexa so CalSync can suggest open appointment windows instead of only listing busy ones

### Endpoints

- `GET /`
- `GET /booking/setup`
- `POST /booking/setup/types/default`
- `POST /booking/setup/types/delete`
- `GET /connections`
- `GET /connections/settings-backup`
- `POST /connections/legacy-backup/import`
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
- Google and Microsoft setup surfaces that now block browser connect actions until the shared OAuth app is actually saved, so tomorrow's provider onboarding path starts from a truthful setup state
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
- that disconnected root workspace now also blocks stale hero stats, next-up copy, and selected appointment detail, so old local appointment rows do not make the product look partially live
- the Apple setup page now also stays truthful when no Apple account exists, so it no longer shows a fake `Family` connected-account state or add-calendar controls before the first Apple account is saved
- that Apple setup page now also lets operators load a recovered legacy Apple calendar hint directly into the form instead of retyping the imported account and calendar values by hand
- that Apple setup page now also auto-loads the recommended recovered Apple hint when no Apple account is connected yet, so the default reconnect screen opens in the right Family state
- the shared readiness and Apple provider surfaces now also acknowledge when recovered Apple hints are available, instead of continuing to read like a generic missing-provider state
- that Apple setup page now also exposes a safe validation action before save, so operators can test a fresh app-specific password and calendar URL without mutating the live vault state
- a first public booking page that uses the same availability search and writable appointment path as the internal workspace
- that public booking flow is now configurable from `/booking/setup`, including invitee-facing copy, default duration, search horizon, success message, and the writable target used for new bookings
- that public booking flow now also respects operator-managed booking weekdays plus daily start and end hours
- that public booking flow now also blocks the invitee-facing availability refresh controls clearly when no writable calendar is connected, so the page does not look half-live during provider setup
- that public booking flow now also aligns its blocked availability, request, and target-card copy with Apple reconnect when legacy recovery hints already exist
- that public booking flow now also aligns blocked direct submit errors with Apple reconnect when legacy recovery hints already exist
- that root schedule workspace now also aligns blocked direct appointment-create submit errors with Apple reconnect when legacy recovery hints already exist
- that stale deep-link appointment edit and cancel routes now also align with Apple reconnect when legacy recovery hints already exist
- that recovery-mode appointment update and cancel API routes now also align with Apple reconnect when legacy recovery hints already exist
- that Alexa scheduling intents now also align blocked recovery-mode voice errors with Apple reconnect when legacy recovery hints already exist
- that Alexa launch, help, and fallback guidance now also align with Apple reconnect when legacy recovery hints already exist, so the public simulator stops coaching blocked calendar reads or writes
- that the root workspace default-target card now also shows the loaded recovered Apple target instead of `No calendar selected` when legacy recovery hints already exist but reconnect is still blocked
- that blocked root and booking-setup target selectors now also name the loaded recovered Apple target instead of falling back to `No writable calendars connected yet` while reconnect is still blocked
- that booking setup now also blocks its save and create actions clearly when no writable calendar is connected, so operators do not accidentally save disconnected public-booking defaults
- that booking setup flow now supports multiple named booking types, each with its own public slug and shareable invitee-facing URL
- that default `/book` route now becomes a booking-type chooser when multiple public booking types exist, while keeping direct `/book/{slug}` links for focused flows
- that booking setup flow now also lets operators make an existing booking type the default public flow or delete a stale type directly from the UI
- that public booking flow now captures the requester name and contact details so operators can follow up without losing that context after the appointment is created
- a first in-product Alexa setup page that links the live endpoint, policy URLs, and skill package download
- a first in-product Cloudflare access form that stores Worker-management credentials securely in the product vault
- a first in-product Alexa edge-settings form that can always save the desired Alexa state in the product vault, then apply Worker Alexa flags live when Cloudflare worker-management permission is configured
- a first in-product Alexa simulator page that previews real voice responses before the final Amazon console turn-on
- that Alexa simulator now also keeps its empty target-calendar and reschedule-calendar helper copy aligned with the Apple recovery path when legacy hints already exist

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

That Apple setup flow now also supports one-time legacy-secret recovery with the original CalSync encryption key when a preserved Apple app-specific password came from an older Pi backup and cannot be decrypted by the current deployment key.

Recovery-aware product guidance now also points operators to enter that original key on Apple setup, instead of implying they must globally restore the deployment encryption key first.

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
- Truthful save-only Alexa action labels before Worker access exists: issue `#74`
- Restore-aware readiness guidance for recovery-shaped deployments: issue `#75`
- Legacy Pi backup import for Apple recovery hints: issue `#76`
- Load recovered Apple backup hints into the setup form: issue `#77`
- Make Apple recovery messaging point to the reconnect step: issue `#78`
- Add safe Apple setup validation before reconnect save: issue `#79`
- Prefer true writable Apple targets in legacy recovery hints: issue `#80`
- Auto-load the recommended Apple recovery hint on reconnect: issue `#81`
- Align Apple recovery guidance with the new auto-loaded reconnect flow: issue `#82`
- Legacy Apple encrypted-secret recovery diagnostics: issue `#108`
- Deploy Alexa Worker recovery guidance live on Cloudflare: issue `#107`
- One-time legacy Apple secret recovery with the original CalSync encryption key: issue `#113`
- Align original-key Apple recovery guidance with the in-product setup flow: issue `#114`
- Hide stale Apple recovery-secret blocker copy on `/connections` after live reconnect: issue `#115`
- Align shared Alexa readiness with the real Cloudflare and account-linking blockers after Apple reconnect: issue `#116`
- Align Alexa setup account-linking intro copy with the already-saved state: issue `#117`
- Align Alexa next-step guidance with the unsaved desired-state flow after account linking: issue `#118`
- Expose real Alexa skill-ID guidance directly on the setup forms: issue `#119`
- Align the remaining Connections Alexa summaries with the desired-state-first guidance: issue `#120`
- Keep `/alexa/setup` truthful when no desired Alexa plan has been saved yet: issue `#121`
- Keep blank Alexa saves from counting as a real desired plan: issue `#122`
- Keep Alexa save responses truthful when no real plan exists: issue `#123`
- Keep Alexa helper copy truthful when the skill ID is still missing: issue `#124`
- Keep Alexa draft state distinct from untouched defaults: issue `#125`
- Keep Alexa simulator truthful while the live plan is still only a draft: issue `#126`
- Keep the Connections Alexa live-route card aligned with the real blocker order: issue `#127`
- Keep the Alexa follow-up docs aligned with the live skill-ID blocker instead of the old Pi token-sync nicety: issue `#130`
- Keep the Alexa setup status line aligned with the real skill-ID blocker instead of the older Worker-ready message: issue `#131`
- Sync Alexa docs and skill-package instructions with the live Worker deployment state: issue `#128`
- Default-deny Alexa Worker requests when the allowed skill list is empty: issue `#129`
- Keep the entire root workspace blocked when no calendar is connected: issue `#83`
- Keep Alexa guidance aligned with account-linking readiness: issue `#84`
- Keep Alexa Step 4 turn-on summary aligned with live prerequisites: issue `#85`
- Keep Alexa Step 4 turn-on summary aligned with writable-calendar readiness: issue `#86`
- Keep Alexa Step 4 turn-on summary aligned with Cloudflare access readiness: issue `#87`
- Keep Alexa Step 4 turn-on summary aligned with desired Alexa state readiness: issue `#88`
- Keep Connections Alexa panel aligned with desired Alexa state readiness: issue `#89`
- Keep Connections Alexa panel aligned with writable-calendar readiness: issue `#90`
- Keep Connections provider next actions truthful before OAuth setup exists: issue `#91`
- Align blocked operator surfaces with Apple reconnect path: issue `#92`
- Align blocked root workspace guidance with Apple reconnect: issue `#93`
- Align Alexa guidance with Apple reconnect path: issue `#94`
- Align booking setup recovery guidance end to end: issue `#95`
- Align workspace capability summary with Apple reconnect: issue `#96`
- Align Alexa simulator readiness with Apple reconnect: issue `#97`
- Align Alexa simulator selector guidance with Apple reconnect: issue `#98`
- Align public booking recovery guidance with Apple reconnect: issue `#99`
- Align public booking submit errors with Apple reconnect: issue `#100`
- Align root appointment submit errors with Apple reconnect: issue `#101`
- Align Alexa recovery-mode scheduling errors with Apple reconnect: issue `#102`
- Non-Alexa recovery guidance now mirrors the legacy Apple encrypted-secret state across blocked root, booking, stale edit/cancel, and appointment API responses: issue `#110`
- Alexa recovery guidance now mirrors the legacy Apple encrypted-secret state across Alexa setup, Connections, and the simulator: issue `#109`
- Legacy Apple encrypted-secret recovery state now tells operators whether the preserved Apple password is reusable with the current key or still needs the original key: issue `#108`
- Fix workspace planner copy regression and live capability messaging: issue `#62`
- First family scheduling UX: issue `#39`
- Scheduling workspace polish: issue `#40`
- Apple live calendar sync into the shared workspace and Alexa: issue `#41`
- Full-stack readiness and Alexa status surface: issue `#43`
- Legacy archive and clean reset: issue `#33`

## Legacy archive

If we need anything from the old system, use the `legacy/pre-chatgpt-brain-reset` branch as the source of truth for that implementation history.
