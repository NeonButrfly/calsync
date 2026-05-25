# CalSync Microsoft Connect And Discovery Design

## Metadata

- Date: 2026-05-24
- Canonical issue: `#22`
- Related issues: `#17`, `#21`, `#23`
- Scope: turn the existing Microsoft provider scaffolding into a real account connection, calendar discovery, and event sync path

## Goal

Make the saved Microsoft OAuth app settings useful by shipping:

- Microsoft OAuth start and callback routes
- encrypted token persistence for Microsoft accounts
- Microsoft calendar discovery through Microsoft Graph
- Microsoft event import into the normalized event store
- Connections-page status that reflects real connected Microsoft accounts

This slice intentionally stops before provider write-back. Write operations stay tracked in issue `#23`.

## Non-Goals

- no Microsoft appointment create, update, reschedule, or cancel yet
- no unified event editor yet
- no Apple/iCloud write-back in this slice
- no public booking pages in this slice
- no invited-user auth expansion in this slice

## Product Behavior

### Provider Settings

`/admin/providers` continues to store the shared Microsoft OAuth app settings.

The page may keep showing the planned callback URL, but once this slice lands that callback becomes a live route rather than future-only scaffolding.

### Connections

`/admin/accounts` should evolve from “Microsoft is scaffold-only” to a real flow:

- if Microsoft settings are missing, explain that Provider Settings must be completed first
- if settings are present, show `Connect Microsoft Account`
- if one or more Microsoft accounts are already connected, show them in the existing connected-accounts table and let operators choose calendars the same way they do for Google and Apple

### Calendars

After the callback succeeds:

- CalSync stores the Microsoft account
- discovers Microsoft calendars
- leaves newly discovered calendars disabled by default
- lets operators assign existing calendar roles such as `Check availability` and `Receive new bookings` where appropriate later

### Sync

Manual sync and worker sync should include Microsoft accounts using the existing sync framework.

Imported Microsoft events should:

- use the normalized local event model
- preserve provider identity and source payload
- participate in duplicate grouping, review, problems, dashboard, and Flightboard the same as Google and Apple events

## OAuth And Provider Model

### Microsoft OAuth

Use the Microsoft identity platform authorization-code flow for a confidential web application.

Deployment assumptions:

- public HTTPS hostname is available for remote usage
- localhost remains valid for local development and direct-host use
- refresh tokens are stored encrypted at rest

Required capabilities:

- authorization URL builder
- code exchange for tokens
- refresh-token access-token renewal
- reconnect-required handling when refresh fails or is revoked
- account identity lookup through Microsoft Graph

### Recommended Scopes

Default shared scopes for this slice:

- `openid`
- `offline_access`
- `User.Read`
- `Calendars.Read`

This keeps the connect-and-sync slice read-only while remaining compatible with later write-capable scope expansion in issue `#23`.

### Callback Rules

The callback URL should be built the same way CalSync already builds external Google URLs:

- prefer saved `Public App URL`
- otherwise use configured `PUBLIC_BASE_URL`
- otherwise fall back to the live request origin

Unlike Google, Microsoft permits broader redirect URI patterns, but CalSync should still prefer the canonical public hostname for deployment clarity and consistent operator setup.

## Data Model

No new tables are required.

Use the existing `ProviderAccount` fields:

- `provider_type = "microsoft"`
- `access_token_encrypted`
- `refresh_token_encrypted`
- `provider_metadata`

Persist Microsoft-specific metadata keys for:

- account subject / object id
- email or principal display value
- scope list
- token expiry
- auth status
- reconnect-required flag
- last auth error
- calendar discovery sync token if later needed
- per-calendar event sync token if later needed

## Graph Endpoints

Use Microsoft Graph v1.0.

Expected initial endpoints:

- authorize: Microsoft identity platform authorize endpoint
- token: Microsoft identity platform token endpoint
- user info / identity: `GET /v1.0/me`
- calendars: `GET /v1.0/me/calendars`
- events: `GET /v1.0/me/calendars/{calendar_id}/events`

This slice can begin with standard event listing instead of more aggressive calendarView optimization. If incremental sync tokens or delta endpoints are needed later, they can be layered on without redesigning the account model.

## Error Handling

Microsoft failures should mirror the Google operator experience:

- configuration missing -> show actionable Provider Settings guidance
- state mismatch -> hard 400
- denied sign-in -> return to Connections with a clean operator message
- missing code -> return to Connections with a clean operator message
- missing refresh token for new account -> fail clearly
- token refresh failure -> mark reconnect required and surface the last auth error
- discovery or fetch failure -> fail the sync run cleanly and preserve logs

## Testing

Add focused coverage for:

- Microsoft OAuth start route with missing settings
- Microsoft OAuth start route building the correct callback
- callback persistence of account metadata and encrypted tokens
- discovery storing calendars disabled by default
- event fetch normalizing Microsoft events into the local event model
- refresh-token renewal and reconnect-required behavior
- Connections page showing `Connect Microsoft Account` only when the shared app is configured

## Documentation And Tracking

Update:

- `README.md`
- `docs/ops.md`
- `docs/prompts/backend.md`

The docs must explicitly say:

- Microsoft account connection is now real
- Microsoft event sync is now real
- Microsoft write-back is still future work under `#23`
