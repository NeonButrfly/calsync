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
