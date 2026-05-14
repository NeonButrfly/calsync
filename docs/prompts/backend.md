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
- keep Google OAuth client credentials in server configuration, not the admin UI
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
- server-configured credentials are the only supported credential source in this phase
- localhost and HTTPS-hostname callbacks are valid; raw LAN IP callbacks are a documented Google limitation
- the connected-accounts admin page now exposes mock and Google onboarding paths
