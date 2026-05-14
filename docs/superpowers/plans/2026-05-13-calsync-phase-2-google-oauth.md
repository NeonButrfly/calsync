# CalSync Phase 2 Google OAuth Implementation Plan

Related GitHub issue: #2
Related design spec: `docs/superpowers/specs/2026-05-13-calsync-phase-2-google-oauth-design.md`

## Objective

Implement Phase 2 of CalSync so an authenticated admin can connect Google accounts through server-configured, browser-based OAuth, discover calendars, enable selected calendars, sync events read-only into the normalized local store, and surface that data through the existing admin views and ICS feeds.

## Scope Boundaries

In scope:

- Google OAuth start and callback routes
- server-configured Google client ID and secret
- callback URL generation and Google redirect compatibility validation
- encrypted Google token storage
- Google account identity capture
- Google calendar discovery
- Google event import with duplicate-safe upsert
- sync token persistence and `410 Gone` full-resync fallback
- admin UI updates for connected Google accounts and sync state
- tests and docs for the operator flow

Out of scope:

- Google write-back
- Apple/iCloud CalDAV
- broad scheduler overhaul
- headless manual OAuth completion flow

## Implementation Steps

### 1. Expand configuration and URL utilities

- add Google OAuth settings to `Settings`
- add helper functions for:
  - Google callback URL generation
  - callback origin compatibility checks
  - operator-facing compatibility messages
- extend existing URL-generation tests to cover localhost, HTTPS hostnames, and blocked raw LAN IP callbacks

### 2. Introduce runtime HTTP client support

- add a runtime HTTP client dependency for Google token, userinfo, discovery, and event API calls
- keep the client usage concentrated in provider services rather than route handlers

### 3. Extend provider persistence and sync metadata

- add an Alembic migration if schema changes are needed
- decide which metadata remains in JSON and which fields need dedicated columns
- persist safe Google metadata such as:
  - account email
  - account subject
  - granted scopes
  - token expiry
  - reconnect-required state
  - calendar sync token
  - event sync token

### 4. Generalize provider adapter and sync orchestration

- extend the provider adapter shape to support:
  - calendar discovery
  - event fetch
  - token refresh
  - incremental sync cursor usage
- keep mock provider working unchanged from the admin/user perspective
- centralize Google-specific full-sync versus incremental-sync rules inside the provider service

### 5. Build the Google provider service

- add `src/calsync/services/providers/google.py`
- implement:
  - authorization URL creation
  - code-for-token exchange
  - optional reconnect/consent retry behavior when refresh token is missing
  - Google account identity fetch
  - access-token refresh
  - calendar discovery with `calendarList.list`
  - event sync with `events.list`
  - `410 Gone` recovery
  - event normalization from Google payloads
- ensure no secrets are logged

### 6. Add connected-account admin routes and UI

- add a dedicated connected-accounts page under the admin shell
- support:
  - viewing current provider accounts
  - mock provider connect
  - Google config-readiness status
  - callback URL preview
  - blocked-callback guidance
  - Google connect start action
  - callback success and error feedback
- update navigation and templates to reflect that the product now has a real provider-management page

### 7. Wire Google sync into existing calendar and sync pages

- ensure discovered Google calendars appear beside mock calendars
- make newly discovered Google calendars default to disabled
- allow manual enable/disable through the existing calendar-management surface
- ensure manual sync and worker sync process Google accounts through the same orchestration path
- surface reconnect-required and last-error states clearly

### 8. Add tests before and alongside behavior changes

- callback URL generation tests
- redirect compatibility validation tests
- OAuth state handling tests
- callback success and failure tests with mocked HTTP responses
- token refresh and revoked-token handling tests
- discovery mapping tests
- Google event normalization tests
- duplicate-safe re-import tests
- `410 Gone` fallback tests
- dashboard/accounts/sync page tests for Google flows

### 9. Update docs and tracking

- update `README.md`
- update `docs/ops.md` if operator guidance changes
- update `docs/prompts/backend.md`
- add issue evidence and note any remaining Google callback limitations

## Verification Plan

- targeted pytest runs while developing:
  - URL/config tests
  - provider tests
  - auth/OAuth route tests
  - page tests
- final full `pytest -v`
- local Docker smoke for:
  - web startup
  - setup/login still intact
  - mock provider still works
- mocked Google integration acceptance through the admin UI flow

## Risks And Mitigations

### Risk: misleading LAN OAuth expectations

Mitigation:

- block invalid raw-IP Google callback attempts in the UI and routes
- document localhost and HTTPS-hostname requirements clearly

### Risk: token and sync state drift

Mitigation:

- centralize Google token handling in one service
- persist sync tokens in provider metadata consistently
- test `410 Gone` recovery explicitly

### Risk: Phase 1 regressions

Mitigation:

- keep mock provider coverage intact
- preserve existing first-run, MFA, ICS, and worker tests
- verify the existing Pi/local flows still pass after the feature lands
