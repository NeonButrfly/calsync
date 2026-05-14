# CalSync Provider Onboarding UI Implementation Plan

Related GitHub issue: #3
Related design spec: `docs/superpowers/specs/2026-05-13-calsync-provider-onboarding-ui-design.md`

## Objective

Replace the current partial provider onboarding model with an admin UI flow that supports:

- deployment-wide Google OAuth credential management in the database
- multiple Google accounts
- multiple Apple/iCloud accounts
- clear separation between provider configuration, account connection, and calendar enablement

## Scope Order

Implement in this order to minimize regression risk:

1. provider configuration storage and UI
2. Google OAuth flow migration from `.env` config to database-backed config
3. connected-accounts UI cleanup for multi-account operation
4. Apple/iCloud account onboarding and discovery
5. docs and deployment validation

## Step 1. Add provider configuration persistence

- add a new model and Alembic migration for provider configuration
- support encrypted secret values and plain text values where appropriate
- add repository and service helpers for:
  - get provider config
  - set provider config
  - determine whether a provider is configured

Tests:

- encrypted secret storage and retrieval
- empty/default config state
- updating existing provider config

## Step 2. Add Provider Settings admin page

- add `/admin/providers`
- create a Google settings form with:
  - client ID
  - client secret
  - optional scopes
  - callback URL preview
  - callback compatibility guidance
- explain the Apple per-account model on the same page
- add navigation link from the admin shell

Tests:

- page requires admin auth
- Google settings save works
- saved values drive readiness state
- callback preview and validation render correctly

## Step 3. Rewire Google OAuth to use DB-backed provider config

- remove the hard dependency on `.env` Google client values for normal app behavior
- preserve `.env` fallback only if intentionally desired for migration or bootstrap
- update Google OAuth routes and provider service to read client ID and secret from provider configuration storage
- keep encrypted token persistence and multi-account behavior

Tests:

- Google start fails cleanly when UI config is missing
- Google start succeeds when UI config exists
- callback succeeds with UI-stored credentials
- multiple Google accounts can coexist

## Step 4. Improve Connected Accounts page for true multi-account use

- group accounts by provider
- show provider configuration readiness
- keep mock provider action
- keep Google connect action
- add Apple/iCloud account form action
- improve account status and reconnect messaging

Tests:

- empty-state guidance
- multiple Google accounts render correctly
- provider status badges reflect auth state

## Step 5. Implement Apple/iCloud account onboarding

- add Apple account form fields:
  - label
  - Apple ID username/email
  - app-specific password
- encrypt and store the app-specific password per account
- implement CalDAV discovery for the account
- surface clear auth/discovery failures
- create discovered calendars disabled by default until explicitly enabled

Tests:

- form validation
- encrypted password persistence
- successful discovery mapping
- auth failure handling
- duplicate-safe rediscovery

## Step 6. Update calendar-management guidance

- update calendars empty state and related helper copy
- make it clear that accounts are added first, then calendars are enabled

Tests:

- dashboard and calendars page copy/flow expectations

## Step 7. Documentation and operator implications

- update README for:
  - provider settings page
  - Google UI-managed credentials
  - Apple add-account flow
  - multiple account model
- update ops docs for:
  - backup sensitivity of database-stored provider secrets
  - secret rotation considerations
- update prompt capture docs

## Step 8. Verification

- targeted test runs while developing
- final `pytest -v`
- `docker compose config`
- `docker compose up --build -d`
- local smoke for:
  - provider settings page
  - connected accounts page
  - Google config persistence
- Pi redeploy after implementation if the user wants the host updated immediately

## Risks And Mitigations

### Risk: secret sprawl increases backup sensitivity

Mitigation:

- encrypt provider secrets at rest
- document that database backups now contain encrypted provider secrets

### Risk: mixing deployment-wide and per-account credentials in the UI confuses operators

Mitigation:

- separate Provider Settings from Connected Accounts
- avoid the phrase “Add calendar” for provider onboarding

### Risk: Phase 2 Google logic regresses while moving config ownership

Mitigation:

- move config reads behind a provider configuration service
- preserve existing Google provider tests and add route-level UI-config tests
