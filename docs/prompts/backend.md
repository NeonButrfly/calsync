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
