# CalSync Phase 1 Foundation Design

Related GitHub issue: #1

## Summary

CalSync Phase 1 delivers a production-grade foundation for a self-hosted, read-only calendar aggregation platform. The first release targets Linux/Unix deployment through Docker Compose, uses FastAPI with server-rendered templates, persists state in PostgreSQL, and provides mandatory MFA-protected admin access, mock-provider-backed event aggregation, and read-only ICS publishing.

This phase intentionally does not implement real Google OAuth, Apple/iCloud CalDAV, or full production sync scheduling behavior. Instead, it establishes the architecture, security model, data model, operator workflows, and test surface required to add those integrations without reworking core systems.

## Goals

- Provide a working Dockerized application reachable on LAN and localhost by default.
- Bind on `0.0.0.0` by default with `APP_PORT=3080`.
- Require first-run admin creation through the web UI with no default credentials.
- Require MFA for all admin accounts with TOTP, QR enrollment, setup key display, and recovery codes.
- Persist setup state, users, calendars, events, feed tokens, and sync metadata in PostgreSQL.
- Support mock-provider calendar discovery and import so the app is useful and testable before real providers are connected.
- Provide combined, grouped, and source-level read-only ICS feed publishing with stable unguessable tokens.
- Establish a clean provider adapter interface for later Google and Apple implementations.
- Ship with operator documentation, emergency local reset commands, and automated tests.

## Non-Goals

- No bidirectional sync.
- No write-back to Google Calendar.
- No write-back to Apple/iCloud calendars.
- No destructive provider actions.
- No public registration flow.
- No reverse proxy requirement for local LAN use.
- No claim of Apple OAuth support.
- No reliance on in-memory-only storage.

## Product Shape

Phase 1 is a modular monolith with a shared codebase and two runtime roles:

- `web`: public/admin HTTP server exposing the UI, health endpoint, auth flows, calendar views, sync status pages, and read-only ICS feeds.
- `worker`: background process container sharing the same application package and database, initially providing manual/mock sync execution scaffolding and the production shape for later scheduled sync work.

Both roles share the same domain, provider, and persistence layers. PostgreSQL is the source of truth for application state. The browser UI reads normalized local data only and never talks directly to provider APIs.

## Runtime And Deployment

### Default configuration

- `APP_HOST=0.0.0.0`
- `APP_PORT=3080`
- `PUBLIC_BASE_URL` optional
- Docker Compose publishes the configured port on the host
- Default access:
  - `http://localhost:3080`
  - `http://SERVER-IP:3080`

### Required startup behavior

Startup logs must clearly report:

- bind host
- bind port
- public/base URL if configured
- healthcheck URL

### Docker topology

Phase 1 Compose stack:

- `web`
- `worker`
- `db` (PostgreSQL)

Persistent volumes:

- PostgreSQL data volume
- optional application data/config volume for generated artifacts if needed

### Health endpoint

A lightweight unauthenticated endpoint, such as `/healthz`, will report process liveness and basic database readiness. Docker healthchecks will use this endpoint.

## Application Architecture

The application is divided into focused modules with clear responsibilities.

### `config`

- Load environment variables and typed settings.
- Resolve bind host/port and base URL behavior.
- Provide security-related configuration such as session secret and encryption key presence.
- Generate callback/feed base URLs using `PUBLIC_BASE_URL` when set, otherwise the incoming request host.

### `auth`

- Admin user persistence and lookup.
- Password hashing and verification.
- Session creation and validation.
- TOTP secret generation and verification.
- Recovery code generation, hashing, validation, and one-time consumption.
- Re-authentication checks for sensitive actions such as token rotation or MFA reset.

### `bootstrap`

- First-run setup gate.
- Setup-complete state persistence.
- Setup route lockout after first admin activation.
- Local emergency operator commands for password and MFA reset without configuration loss.

### `providers`

- Provider adapter interface.
- Mock provider implementation in Phase 1.
- Data contracts for account discovery, calendar discovery, event import, and sync status.
- Future extension points for `google` and `icloud_caldav`.

### `calendars`

- Connected provider accounts.
- Discovered source calendars.
- Enable/disable state for aggregation.
- Group/category assignments.

### `events`

- Local normalized event storage.
- Idempotent upsert logic to avoid duplicates across repeated imports.
- Child records for attendees and reminders.
- Recurrence, timezone, etag/version, and raw provider payload handling.

### `publishing`

- ICS feed token generation.
- Combined, grouped, and source-level feed assembly.
- Token rotation behavior.

### `sync`

- Sync request dispatch for mock/provider accounts.
- Persisted last sync time, last error, event counts, and token/auth state.
- Worker-facing job structure that later expands into interval scheduling, backoff, and retry behavior.

### `ui`

- Server-rendered templates.
- Lightweight progressive JavaScript for better form UX and admin actions.
- No SPA dependency for Phase 1.

## Security Model

### Admin identity

- Login uses `username or email` plus password.
- Every admin account requires MFA.
- Public registration is disabled.
- Only first-run setup may create the first admin.
- Later users may only be created by an authenticated admin in future phases.

### Password requirements

Passwords must be validated for strength during first-run setup and password resets. The exact rule can be implementation-defined, but it must reject weak passwords and be covered by tests.

### MFA requirements

During first-run setup:

1. Collect username/email, password, and confirmation.
2. Generate a unique TOTP secret.
3. Generate an `otpauth://` URI.
4. Render a QR code in the UI.
5. Display the plain setup key for manual entry.
6. Generate recovery codes and display them once.
7. Require a valid 6-digit TOTP code before account activation completes.
8. Require acknowledgment that recovery codes were stored before completion.

During normal login:

1. Verify username/email and password.
2. Require a valid TOTP code or unused recovery code.
3. Establish an authenticated admin session only after MFA succeeds.

### Secret storage

The application should encrypt secrets at rest where feasible using an application encryption key loaded from environment:

- TOTP secrets
- provider refresh tokens in later phases
- Apple app-specific passwords in later phases

Recovery codes are not encrypted for reuse. They are stored only as hashes and compared on use.

### Logging constraints

The application must never log:

- passwords
- password reset values
- TOTP secrets
- QR payloads
- recovery codes
- OAuth tokens or codes
- Apple app-specific passwords
- raw authorization headers

Operational logs may record that a reset or rotation occurred, but not the secret values involved.

### Break-glass local reset commands

Phase 1 includes local-only operator commands:

- reset an admin password without touching providers, calendars, groups, feeds, sync state, or event data
- reset MFA enrollment for an admin without touching any other configuration

These commands are designed for container shell or host-side local execution only and are documented as emergency procedures.

## Data Model

### `admin_users`

- `id`
- `username`
- `email`
- `password_hash`
- `totp_secret_encrypted`
- `mfa_enrolled`
- `is_active`
- `created_at`
- `updated_at`
- `last_login_at`

### `recovery_codes`

- `id`
- `admin_user_id`
- `code_hash`
- `used_at`
- `created_at`

### `app_state`

Singleton-style application settings and flags:

- `setup_complete`
- schema or application version metadata
- default sync interval settings when Phase 4 arrives

### `provider_accounts`

- `id`
- `provider_type`
- `display_name`
- `external_account_id`
- `status`
- encrypted secret/token fields
- `last_sync_at`
- `last_error`
- `created_at`
- `updated_at`

### `provider_calendars`

- `id`
- `provider_account_id`
- `provider_calendar_id`
- `name`
- `timezone`
- `color`
- `enabled`
- `group_id`
- sync cursor/token fields where applicable in later phases
- `last_sync_at`
- `last_error`

### `calendar_groups`

- `id`
- `name`
- `slug`
- `created_at`
- `updated_at`

### `events`

Uniqueness is enforced on the logical provider identity to prevent duplicates on repeated import:

- provider
- source account
- source calendar
- provider event id

Event fields include:

- `title`
- `location`
- `description`
- `timezone`
- `start_at`
- `end_at`
- recurrence data
- provider etag/version
- safe raw provider payload
- `is_cancelled` if needed later
- timestamps

### `event_attendees`

- `event_id`
- attendee identity/details as available
- RSVP or role metadata where available

### `event_reminders`

- `event_id`
- reminder type/offset data where available

### `published_feeds`

- `id`
- feed scope type: `combined`, `group`, `source`
- related group/calendar reference
- stable random token
- created/rotated timestamps
- optional disabled/revoked state

### `sync_logs`

- `id`
- provider account and optional calendar reference
- sync trigger type
- start/end timestamps
- outcome status
- event counts
- sanitized error summary

## First-Run Setup Behavior

On startup, the app checks whether any admin user exists and whether setup is complete.

- If no admin exists and setup is incomplete, the app exposes only first-run setup and health endpoints.
- If setup is complete, the first-run setup route is inaccessible.
- The setup flow is not shown again after the initial admin is activated.

The first-run setup sequence ends only after:

- password validation passes
- password confirmation matches
- TOTP verification succeeds
- recovery codes were generated and displayed
- the setup-complete state is written to the database

## Admin UI Scope

Phase 1 server-rendered pages:

- first-run setup
- login
- MFA challenge
- dashboard
- connected accounts
- calendars
- combined calendar view
- sync status
- ICS publishing/token management

### Dashboard

Shows:

- setup summary
- account count
- enabled calendar count
- event count
- feed shortcuts
- recent sync status

### Connected accounts

Phase 1 supports mock-provider-backed accounts only. The page is still shaped like the future real-provider management surface so Google and Apple can plug in later.

### Calendars

Shows discovered calendars, per-calendar enable/disable state, and group assignment controls.

### Combined calendar view

A simple usable month/list-capable view is sufficient. It must read normalized local data only and show that aggregation is functioning.

### Sync status

Shows:

- last sync time
- last error
- number of events synced
- auth/token status as applicable
- manual sync action

### ICS publishing

Shows the available read-only feeds for:

- combined calendar
- grouped calendars
- source calendars

Each feed uses a stable unguessable token and supports token rotation.

## Mock Provider Mode

Mock provider mode is a first-class feature in Phase 1, not a test hack.

It must:

- create deterministic sample accounts/calendars/events
- include recurring and non-recurring events
- exercise the same normalization path as real providers
- populate local sync status and event counts
- allow repeated imports without duplicate events

This makes the application demonstrably useful and fully testable before external credentials are introduced.

## ICS Publishing

Feed endpoints are read-only and token-protected. Tokens must be generated from strong randomness and remain stable until rotated.

Feed types:

- per source calendar
- per group/local calendar
- one combined calendar

Base URL behavior:

- use `PUBLIC_BASE_URL` when configured
- otherwise derive URLs from the request host

This ensures LAN usability without requiring a reverse proxy.

## URL And Callback Strategy

Phase 1 itself only needs accurate feed/admin URL generation, but the config layer must already support later OAuth callback generation.

Rules:

- `APP_HOST` controls server binding, not external callback generation
- `APP_PORT` defaults to `3080`
- `PUBLIC_BASE_URL`, when set, is the canonical externally advertised base URL
- when `PUBLIC_BASE_URL` is not set, generated URLs use the incoming request origin

This strategy supports:

- `http://localhost:3080`
- `http://SERVER-IP:3080`
- future LAN/headless OAuth redirect documentation

## Worker Shape And Sync Foundation

Phase 1 includes a separate worker container so the production topology is honest from day one.

Initial worker responsibilities:

- accept/manual trigger sync jobs
- run mock-provider sync
- persist sync results

Future Phase 4 additions:

- periodic scheduling
- retry/backoff
- incremental sync token handling
- provider token refresh behavior
- richer sync dashboards

The sync state model must survive restarts so no essential state lives only in memory.

## Testing Strategy

Phase 1 automated tests must cover:

- first-run setup succeeds correctly
- first-run setup cannot repeat after admin exists
- password validation
- TOTP secret generation
- `otpauth://` URI formatting
- QR code generation
- successful TOTP verification
- failed TOTP verification
- recovery code one-time use
- login requires MFA
- mock-provider discovery
- event normalization
- duplicate prevention
- ICS generation
- token rotation
- URL generation behavior

Tests should use mock providers and isolated test database state. The suite should validate behavior, not only implementation details.

## Documentation Requirements

Phase 1 documentation must include:

- project overview
- local setup
- Docker Compose deployment
- `.env` configuration
- bind host/port defaults
- how to change `APP_PORT`
- first-run admin setup
- MFA enrollment and recovery code handling
- break-glass local password reset
- break-glass local MFA reset
- LAN access notes
- backup and restore guidance
- known limitations
- roadmap note that real Google and Apple providers arrive in later phases

Documentation must reference GitHub issue `#1` as the Phase 1 tracking source.

## Future Phase Compatibility

### Phase 2

Add `providers/google` with:

- OAuth 2.0 connection flow
- refresh token storage
- calendar discovery
- read-only event import
- callback URL generation using the same config/base URL utilities

### Phase 3

Add `providers/icloud_caldav` with:

- Apple ID username plus app-specific password
- CalDAV discovery
- read-only event import
- clear auth error reporting

### Phase 4

Expand worker/sync features:

- background scheduling
- retry/backoff
- incremental sync where supported
- token refresh handling
- visible sync state dashboard details

## Risks And Mitigations

### Risk: auth/security complexity overwhelms Phase 1

Mitigation:

- keep UI server-rendered
- implement one admin role only
- keep MFA mandatory and uniform
- test first-run and login flows heavily

### Risk: provider-specific assumptions leak into the foundation

Mitigation:

- require provider adapters to emit normalized data contracts
- validate all UI and ICS behavior against local normalized data only

### Risk: local/LAN deployment drift

Mitigation:

- centralize host/port/base URL settings
- test URL generation directly
- document Compose port changes clearly

### Risk: emergency resets become destructive

Mitigation:

- separate credential resets from configuration/state deletion
- explicitly preserve accounts, calendars, groups, feeds, events, and sync logs

## Acceptance For The Phase 1 Deliverable

The Phase 1 deliverable is accepted when:

- Docker Compose starts the app on Linux/Unix
- the app listens on all interfaces by default
- the app is reachable at `http://localhost:3080`
- the app is reachable at `http://SERVER-IP:3080`
- changing `APP_PORT` changes the exposed host port
- first-run admin creation works from the web UI
- admin activation requires valid TOTP confirmation
- no default admin account exists
- login requires password and MFA
- mock calendars can be discovered, enabled, grouped, and viewed
- combined/source/group ICS feeds are generated and consumable
- sync state survives restart
- no secrets are emitted in logs

## Recommendation

Implement this design as a production-grade Phase 1 vertical slice tied to GitHub issue `#1`, then add Google, Apple, and richer background sync features in subsequent tracked phases without restructuring the foundation.
