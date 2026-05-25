# Backend Prompt Capture

- GitHub issue: `#1`
- Scope: Phase 1 foundation for a read-only calendar aggregation service

## Interpreted Requirements

- provide a Linux and Docker Compose friendly deployment with `APP_HOST=0.0.0.0` and `APP_PORT=3080`
- require first-run admin setup instead of shipping a default account
- require mandatory MFA with TOTP, QR enrollment, and recovery codes
- provide local break-glass recovery commands
- keep all provider behavior read-only
- publish read-only ICS feeds with stable unguessable tokens
- support a mock provider mode so the app can be validated before Google or Apple credentials exist

## Behavioral Boundaries

- mandatory MFA stays enabled for admin access
- provider access is read-only
- no Google write-back
- no Apple write-back
- no destructive provider actions

## Phase Notes

- Phase 1 uses the mock provider and the normalized local event model
- Google OAuth setup is documented for Phase 2
- Apple app-specific password and CalDAV integration are documented for Phase 3

---

- GitHub issue: `#2`
- Scope: Phase 2 Google OAuth calendar discovery and read-only sync

## Interpreted Requirements

- add Google account connection through a browser-based OAuth flow
- initially keep Google OAuth client credentials in server configuration before broader onboarding changes
- preserve the existing Dockerized FastAPI/Postgres/worker foundation
- import Google calendars and events read-only into the local normalized store
- keep combined calendar views and ICS feeds powered from local normalized data
- document the real callback limitations for localhost versus raw LAN IP use

## Behavioral Boundaries

- Google access remains read-only
- no event creation, update, or deletion upstream
- no public provider registration flow
- no fake support for raw-IP Google redirect URIs
- no Apple/iCloud work in this phase

## Phase Notes

- Google OAuth is Phase 2 and is tracked in issue `#2`
- browser-based OAuth is supported in this phase; manual headless completion is deferred
- server-configured credentials were the first supported credential source in this phase
- localhost and HTTPS-hostname callbacks are valid; raw LAN IP callbacks are a documented Google limitation
- the connected-accounts admin page now exposes mock and Google onboarding paths

---

- GitHub issue: `#3`
- Scope: UI-managed provider onboarding for multiple Google and Apple accounts

## Interpreted Requirements

- Google OAuth client ID and secret should be settable in the admin UI
- the app should support multiple Google accounts
- the app should support multiple Apple/iCloud accounts
- onboarding should gather provider or account credentials in the interface
- discovered calendars should be enabled after account connection, not manually credentialed one by one

## Behavioral Boundaries

- provider onboarding remains read-only
- Google client credentials are deployment-wide configuration, not per-calendar data
- Apple credentials are per-account data
- the UI should say add or connect account, not imply each calendar is configured manually

## Phase Notes

- issue `#3` supersedes the earlier server-config-only Google credential assumption for future onboarding work
- the onboarding model is now provider settings -> connected accounts -> discovered calendars
- issue `#3` is now implemented in the app
- Google deployment credentials can be managed in the admin UI with environment fallback available for bootstrap
- Apple/iCloud accounts can be added directly in the admin UI with app-specific passwords
- Google setup docs now explicitly explain that one Google OAuth web client can authorize multiple Google accounts, with separate consent per account and test-user requirements while the Google app remains in testing mode
- successful Google and Apple account connections now route directly into calendar selection, and connected accounts expose a direct choose-calendars action

---

- GitHub issue: `#4`
- Scope: public app URL management, domain-backed Google onboarding, and private flightboard view

## Interpreted Requirements

- admins should be able to save a canonical public app URL in the UI
- that setting should be presented as `Public App URL` in `Provider Settings`
- Google account connection should use that saved HTTPS hostname when present
- the first real deployment target is `https://calsync.neonbutterfly.net`
- Google connect should remain available even when the admin browses from LAN or localhost, as long as the saved public URL is valid
- the Accounts page should continue to expose `Connect Google Account` when the saved public hostname satisfies the callback requirement
- generated external links should prefer the saved public URL
- the app should provide a private scrolling flightboard-style view of enabled calendars at `/admin/flightboard`

## Behavioral Boundaries

- the flightboard remains private and admin-only
- no reverse proxy automation is added inside CalSync
- no public anonymous board is introduced in this phase
- provider access remains read-only

## Phase Notes

- issue `#4` uses `https://calsync.neonbutterfly.net` as the first real target hostname
- operator docs should tell admins to save that hostname in `Public App URL` before remote Google onboarding
- Google callback messaging should explain the exact hostname that will be used
- the Accounts page should clearly route operators from `Provider Settings` to `Connect Google Account`
- the flightboard view should read from the normalized local event store and only include enabled calendars
- the private Flightboard route is `/admin/flightboard`

---

- GitHub issue: `#5`
- Scope: private Flightboard auto-scroll and current/upcoming day-week-month views

## Interpreted Requirements

- the private Flightboard should scroll automatically for operations viewing
- the Flightboard should support `Day`, `Week`, and `Month` display ranges
- the Flightboard should only show current and upcoming events
- the Flightboard should never show events that have already ended

## Behavioral Boundaries

- the Flightboard remains private and admin-only
- the Flightboard continues to read from normalized local event data only
- no public anonymous signage route is introduced

## Phase Notes

- issue `#5` extends the existing private Flightboard from issue `#4`
- the default board should emphasize current and upcoming activity rather than historical events
- range switching should stay inside `/admin/flightboard`

---

- GitHub issue: `#6`
- Scope: restore private Flightboard auto-scroll for short event lists

## Interpreted Requirements

- the private Flightboard auto-scroll should still move when only a short list of current or upcoming events is available
- the board should remain useful for unattended operations viewing even before many events are enabled
- the Flightboard should keep the column header static above the scrolling rows without overlapping event content
- the Flightboard should provide an explicit enable or disable auto-scroll button
- the chosen auto-scroll setting should be remembered in the browser for later visits

## Behavioral Boundaries

- the Flightboard remains private and admin-only
- the board still pauses on hover
- historical events remain excluded

## Phase Notes

- issue `#6` hardens the existing Flightboard auto-scroll behavior from issue `#5`
- the client can duplicate visible rows for scrolling only when the rendered list is too short to overflow naturally

---

- GitHub issue: `#7`
- Scope: preserve enabled Google calendars across incremental discovery so new events continue syncing

## Interpreted Requirements

- enabled Google calendars must stay enabled after later incremental discovery cycles that return no changed calendar items
- newly created events on already-enabled Google calendars should continue importing without the account silently losing its calendar selections

## Behavioral Boundaries

- Google access remains read-only
- incremental Google discovery must not treat an empty change set as a full replacement of the account calendar list

## Phase Notes

- issue `#7` fixes a regression where empty incremental Google calendar-list responses disabled all discovered Google calendars
- explicit deleted calendars can still be disabled through discovery metadata without treating unchanged calendars as removed

---

- GitHub issue: `#8`
- Scope: convert UI-facing UTC timestamps into Alaska time

## Interpreted Requirements

- dashboard, sync-status, and other admin-facing timestamp displays should render in Alaska time
- UTC-backed event and sync timestamps should not leak raw UTC values into the UI
- the flightboard should convert UTC-backed calendar events into Alaska display time as well

## Behavioral Boundaries

- provider and database storage remain UTC-backed and unchanged
- only display formatting changes for the admin UI
- the UI should render Alaska-local display times with a consistent `AKST` label

## Phase Notes

- issue `#8` introduces a shared Alaska display formatter for Jinja-rendered admin pages
- UTC or timezone-missing datetimes should be treated as UTC before converting for display

---

- GitHub issue: `#10`
- Scope: deployment self-recovery after host reboot or Docker restart

## Interpreted Requirements

- the long-running deployment services should come back automatically after a host reboot or Docker daemon restart
- operators should not need to manually run `docker compose up -d` after every unplanned host restart
- the one-shot migration service should remain a normal run-once step rather than a continuously restarting service

## Behavioral Boundaries

- automatic restart applies to `db`, `web`, and `worker`
- the migration service remains a run-once container
- operator-initiated stops should still remain stopped until the operator starts the stack again

## Phase Notes

- issue `#10` adds `restart: unless-stopped` to the long-running Compose services
- README and ops docs should describe the reboot-recovery expectation and verification flow

---

- GitHub issue: `#11`
- Scope: turn CalSync into a more trustworthy personal scheduling utility with sync hygiene, dedupe, and extensible appointment ingestion

## Interpreted Requirements

- keep connected calendars current and useful rather than merely aggregated
- remove stale, obsolete, cancelled, or upstream-deleted items from active schedule views
- resolve or suppress duplicate calendar entries across multiple connected sources
- preserve source provenance while presenting cleaner canonical events
- prepare source hooks for appointment-oriented systems beyond standard calendar providers
- create a safe path for future portal-based or reminder-derived appointment ingestion

## Behavioral Boundaries

- all ingestion remains read-only
- no generic promise of arbitrary portal scraping
- no direct server-side ingestion of iCloud phone backups as the first message-derived source path
- trust and cleanup work should land before harder new connectors

## Phase Notes

- issue `#11` is a product-expansion umbrella, not a single bugfix
- the first recommended implementation slice is event trust and cleanup
- Athena-style portal work should be treated as a gated future adapter requiring a real supported auth path
- reminder or message-derived appointment capture should enter through a generalized source adapter model rather than through direct backup parsing

---

- GitHub issue: `#15`
- Scope: direct problem inbox actions and per-event explainability for trust cleanup

## Interpreted Requirements

- `/admin/problems` should offer provider-aware duplicate actions instead of only sending the operator into review
- duplicate action links and redirects must stay stable even when duplicate groups are recalculated
- manual `show both` style decisions must persist across duplicate rebuilds
- the app should expose `/admin/events/{event_id}` as a private explanation surface for one appointment copy
- operators should be able to understand why one copy is preferred, hidden, or still visible without hunting through multiple pages

## Behavioral Boundaries

- duplicate cleanup remains read-only with respect to upstream providers
- CalSync hides or reveals local normalized copies; it does not delete provider source records
- private trust and explain routes stay behind admin authentication

## Phase Notes

- issue `#15` adds `Keep Google copy`, `Keep iCloud copy`, `Show all copies`, and `Explain this event` to the problem-to-fix inbox
- duplicate group anchors are now based on stable member event ids rather than ephemeral rebuilt group ids
- `/admin/events/{event_id}` shows grouped source copies, visibility state, and latest sync context for the selected appointment
- active views now suppress `deleted_upstream`, `cancelled`, and hidden duplicate copies
- full discovery can retire events from calendars that disappear upstream instead of leaving zombie active items behind
- duplicate cleanup is now exposed through `/admin/review`

---

- GitHub issue: `#12`
- Scope: make duplicate and trust state intuitive and operator-fixable

## Interpreted Requirements

- the app should make common calendar mistakes easy to understand and fix
- the operator should be able to see likely duplicate appointments from one obvious page
- the operator should be able to keep the right copy when the same appointment was added twice
- the dashboard should surface trust state instead of hiding all cleanup logic in the backend

## Behavioral Boundaries

- duplicate handling remains conservative and read-only
- raw provider events are preserved internally even when extra copies are hidden from active views
- restore actions should be available when both copies should remain visible

## Phase Notes

- issue `#12` builds on the lifecycle foundation from issue `#11`
- `/admin/review` is the operator-facing trust and duplicate cleanup page
- hidden duplicate decisions persist across normal refreshes

---

- GitHub issue: `#13`
- Scope: broaden trust cleanup so CalSync feels smarter and easier to use during normal calendar review

## Interpreted Requirements

- the app should catch obvious duplicate appointments even when one copy has small title drift or small time drift
- the main dashboard should show one canonical appointment row instead of listing every provider copy separately
- the operator should be able to see when one appointment is backed by multiple synced sources
- duplicate cleanup should feel like a visible `Needs attention` queue rather than a hidden backend heuristic

## Behavioral Boundaries

- duplicate grouping stays conservative and read-only
- the system hides extra copies from active views instead of deleting source records
- a preferred copy remains operator-overridable through `/admin/review`

## Phase Notes

- issue `#13` builds on the trust-review foundation from issue `#12`
- the dashboard combined view now shows one row per active canonical appointment and adds a source-count badge when multiple provider copies are grouped
- `/admin/review` now exposes `Needs attention` language for the duplicate cleanup queue

---

- GitHub issue: `#14`
- Scope: add a single problem-to-fix inbox so CalSync clearly shows what looks wrong and how to resolve it

## Interpreted Requirements

- the operator should have one obvious page that answers "what needs attention right now?"
- duplicate cleanup, sync retry problems, and account reconnect problems should be surfaced in one normalized list
- the dashboard should summarize open problems and link into the inbox
- where a safe action already exists, the inbox should offer it directly instead of forcing the operator to hunt through the app

## Behavioral Boundaries

- the inbox is an operator workflow layer over existing trust and sync state, not a destructive reconciliation engine
- duplicate items should link into the trust review flow for final operator choice
- sync retry actions may run directly from the inbox because they are already supported, non-destructive operations

## Phase Notes

- issue `#14` builds on issues `#12` and `#13`
- `/admin/problems` is the new problem-to-fix inbox
- `/admin` now includes a `Problems to fix` summary card

---

- GitHub issue: `#15`
- Scope: add direct problem inbox actions and a per-event explain view so operators can understand and fix trust issues without hunting through the app

## Interpreted Requirements

- duplicate problem cards should offer more useful direct actions instead of only redirecting elsewhere
- operators should be able to inspect one event and understand its source copies, preferred state, and sync context
- the problem inbox should stay action-oriented while the explain page becomes the deeper inspection surface

## Behavioral Boundaries

- duplicate fixes remain local visibility and preference changes only
- no provider write-back or raw event deletion is introduced
- provider-specific keep actions only appear when that provider has a copy in the grouped appointment

## Phase Notes

- issue `#15` builds on the problem inbox from issue `#14`
- `/admin/problems` should gain richer duplicate actions and an `Explain this event` path
- `/admin/events/{event_id}` should become the operator deep-dive view for event trust state

---

- GitHub issue: `#16`
- Scope: rank the post-trust roadmap and start source-confidence utility work

## Interpreted Requirements

- the product should have a ranked roadmap for becoming a best-in-class private calendar integrator instead of only a loose future-work list
- the next immediate slice should deepen trust by teaching CalSync why one source copy should win and how to remember that decision
- future phases should be sequenced deliberately around trust, connector reach, saved views, availability, and scheduling intelligence

## Behavioral Boundaries

- all roadmap work remains read-only with respect to providers
- the first next slice should extend the existing trust engine rather than jumping straight into portal scraping or message-backup ingestion
- new roadmap ideas should be staged under the utility-expansion umbrella in issue `#11` instead of becoming untracked feature drift

## Phase Notes

- issue `#16` breaks the post-trust roadmap out of umbrella issue `#11`
- the recommended next implementation slice is source confidence and sticky provider preference policies
- later roadmap phases should include a connector SDK, email or ICS reminder ingestion, calendar sets and saved views, availability or booking links, and deeper scheduling intelligence

---

- GitHub issue: `#17`
- Scope: redesign CalSync into a write-capable scheduling product with cleaner calendar connections, invited-user foundations, and brighter UX

## Interpreted Requirements

- the app should evolve beyond a read-only aggregator and support creating, editing, rescheduling, and cancelling appointments on writable providers
- Google and Microsoft calendar connections should feel like normal public web sign-in flows on the existing public hostname
- Apple/iCloud should keep the current CalDAV plus app-specific-password connector path
- existing Apple connector data and stored app-specific passwords must be preserved
- the product should be reshaped toward a clean scheduling experience with connections, availability, booking pages, and trust surfaces
- future identity planning should include email and password plus MFA, Sign in with Google, Sign in with Microsoft, Sign in with Apple, and invited-user onboarding

## Behavioral Boundaries

- the redesign remains single-tenant with invited users first
- no fake Apple calendar OIDC flow is introduced
- the current Apple connector must not be lost during migration
- write-back must be explicit and role-aware rather than silently writing to every connected calendar

## Phase Notes

- issue `#17` supersedes the earlier strictly read-only product direction for the long-term architecture
- the recommended first implementation slice is the product refactor foundation plus the start of writable Google and Microsoft provider architecture
- the product should keep trust and problem-fix workflows while moving toward a cleaner scheduling-app UX
- the shipped foundation slice now uses a brighter scheduling workspace shell with `Connections`, `Availability`, `Trust`, and `Settings` framing
- the current `Connections` experience lives on `/admin/accounts` and groups Google, Microsoft, Apple, and mock onboarding without losing existing account data
- Apple connector data and stored app-specific passwords are preserved during the redesign
- calendar roles now exist so operators can mark calendars for `Check availability` or `Receive new bookings`
- writable booking targets are only valid for writable provider accounts; read-only providers stay availability-only
- Microsoft begins as shared OAuth app and connection groundwork in this umbrella, with live account connection, discovery, and read-only sync later shipped under issue `#22`
- no full booking pages in this slice
- provider write-back remains follow-on work under issue `#23`

---

- GitHub issue: `#21`
- Scope: expose Microsoft OAuth app settings in Provider Settings as the groundwork step before Microsoft account-connect ships in issue `#22`

## Interpreted Requirements

- the shared Microsoft OAuth client ID, secret, and scopes should be operator-visible and editable in `Provider Settings`
- the app should show the planned Microsoft callback URL so operators can understand the future deployment shape
- the Connections page should reflect whether the shared Microsoft app has already been saved
- the product must stay honest that this issue only delivers the shared app-settings groundwork, not the later account-connect slice

## Behavioral Boundaries

- no real Microsoft OAuth connect flow is introduced in this issue itself
- no Microsoft calendar discovery or event sync is introduced in this issue itself
- the callback URL shown in `Provider Settings` is a planned future callback target, not an active live route for account connection

## Phase Notes

- issue `#21` builds on the write-capable foundation in issue `#17`
- `Provider Settings` now exposes a `Microsoft OAuth App` section
- blank or malformed Microsoft scope input should normalize to the default shared scopes instead of persisting a misleading broken configuration
- Connections should show whether the shared Microsoft app settings are already saved while still treating live Microsoft account connection as later work that lands in issue `#22`

---

- GitHub issue: `#22`
- Scope: ship Microsoft OAuth account connection, calendar discovery, and read-only sync on the write-capable foundation slice

## Interpreted Requirements

- use the shared Microsoft OAuth app settings from `Provider Settings` to support real Outlook / Microsoft 365 account connection
- support one shared Microsoft OAuth app with multiple connected Microsoft accounts
- allow connected Microsoft accounts to discover calendars before operators choose which calendars to enable
- import Microsoft calendar events read-only into the normalized local event store through the existing worker loop
- keep the Connections and Availability product framing aligned with the live Microsoft slice
- make the latest shipped reality clear without collapsing the broader redesign umbrella in issue `#17`

## Behavioral Boundaries

- Microsoft account connection, calendar discovery, and sync are now live in this slice
- Microsoft access remains read-only
- no Microsoft event creation, update, reschedule, or cancellation is introduced here
- no booking pages or public scheduling surfaces are introduced here
- provider write-back remains future work under issue `#23`

## Phase Notes

- issue `#22` builds directly on the Microsoft OAuth app groundwork from issue `#21`
- issue `#17` remains the umbrella redesign for the write-capable scheduling product direction
- `Provider Settings` is the shared Microsoft OAuth configuration surface
- `/admin/accounts` now exposes live Outlook / Microsoft 365 account connection
- `/admin/calendars` remains the operator surface for enabling discovered Microsoft calendars
- the worker sync loop now refreshes Microsoft provider accounts alongside Google and Apple read-only accounts
