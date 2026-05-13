# CalSync Phase 2 Google OAuth Design

Related GitHub issue: #2

## Summary

Phase 2 adds the first real provider integration to CalSync: Google Calendar via server-configured, browser-based OAuth 2.0. This phase builds on the completed Phase 1 foundation and keeps the product strictly read-only. Admins will be able to connect Google accounts, discover calendars, enable selected calendars for aggregation, sync events into the normalized local event store, and surface those events through the existing dashboard, combined calendar view, sync status page, and ICS feeds.

This phase does not add Google write-back, event deletion upstream, Apple/iCloud support, or a broad provider-management redesign. It is a focused Google provider slice on top of the existing architecture.

## Goals

- Add Google account connection using the web-server OAuth 2.0 flow.
- Keep Google OAuth client credentials in server configuration, not the admin UI.
- Support browser-based OAuth completion, suitable for a self-hosted operator workflow.
- Discover calendars for each connected Google account.
- Import Google events read-only into the existing normalized event model.
- Preserve duplicate-safe upsert behavior across repeated syncs.
- Store refresh and access tokens encrypted at rest.
- Reuse the existing UI, worker, sync log, and ICS publishing flows.
- Document the real Google redirect-URI constraints for localhost and LAN deployments.

## Non-Goals

- No bidirectional sync.
- No Google event creation, editing, or deletion.
- No public Google connect flow outside the authenticated admin UI.
- No Apple/iCloud CalDAV in this phase.
- No attempt to bypass Google redirect URI rules for raw LAN IP callbacks.

## External Constraints Verified For This Design

This design is grounded in current Google primary-source documentation reviewed on 2026-05-13.

### OAuth flow constraints

- Google’s web-server OAuth flow supports offline access through `access_type=offline`.
- Google recommends `include_granted_scopes=true` for incremental authorization.
- Google only returns a refresh token when offline access is requested, and refresh-token behavior is sensitive to whether consent has already been granted.
- Google redirect URIs for web applications must use HTTPS, except localhost URIs.
- Raw IP addresses are not allowed as redirect URI hosts, except localhost IP addresses.

### Calendar API constraints

- `calendarList.list` supports discovery and incremental sync with `nextSyncToken`.
- `events.list` supports incremental sync with `syncToken`.
- If a sync token expires, Google returns HTTP `410 Gone` and the client must clear the sync token and perform a new full synchronization.
- Several filter parameters cannot be combined with `syncToken`, including `timeMin`, `timeMax`, and `updatedMin`.

### Practical implication for self-hosted LAN use

The application itself will continue to work on `http://SERVER-IP:3080` for normal UI and ICS access. However, Google OAuth callback registration does not allow raw LAN IP redirect URIs. That means:

- `http://localhost:3080/...` is valid for OAuth when the admin completes the flow on the same machine.
- `http://SERVER-IP:3080/...` is not a valid Google OAuth redirect URI when `SERVER-IP` is a raw IP.
- For non-localhost browser-based Google connect flows, operators need an HTTPS hostname or domain that can be registered with Google.

The product must document this clearly and must not pretend that raw-IP LAN callbacks are supported by Google when they are not.

## Product Behavior

### Admin operator flow

1. Admin signs in with password and MFA.
2. Admin opens the connected accounts page and chooses Google.
3. CalSync validates that the callback base URL is compatible with Google’s redirect URI rules.
4. If the callback base URL is not compatible, the UI blocks the action and explains the fix:
   - use localhost on the host machine, or
   - configure `PUBLIC_BASE_URL` to an HTTPS hostname that matches a registered Google redirect URI
5. If the callback base URL is compatible, CalSync redirects the browser to Google.
6. Google returns to CalSync’s callback route.
7. CalSync exchanges the code for tokens, securely stores them, and identifies the account.
8. CalSync immediately discovers Google calendars for that account.
9. Discovered calendars appear in the calendar management page.
10. Admin enables the desired calendars for aggregation.
11. Manual sync or worker sync imports events into the local store.
12. The existing calendar UI and ICS feeds begin reflecting the Google-backed data.

### Read-only guarantee

The Google integration only uses read scopes and only calls read endpoints. No provider mutation endpoints are implemented or exposed. The UI wording and documentation should reinforce that the Google connection is read-only.

## Configuration

Phase 2 adds server-managed Google configuration to `.env` and `.env.example`.

Required:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`

Optional:

- `GOOGLE_OAUTH_SCOPES`
- `GOOGLE_OAUTH_REDIRECT_PATH`

Default scope set:

- `openid`
- `email`
- `profile`
- `https://www.googleapis.com/auth/calendar.readonly`

Rationale:

- `calendar.readonly` provides read-only calendar and event access.
- `openid email profile` lets the app identify the connected Google account and show a usable display name without inventing identities.

Default redirect path:

- `/auth/google/callback`

The callback URL base is still derived from:

- `PUBLIC_BASE_URL` when configured
- otherwise the incoming request origin

## URL And Redirect Strategy

### Canonical callback URL

The Google callback URL is built from:

- callback base origin
- Google callback path

Example:

- `http://localhost:3080/auth/google/callback`
- `https://calendar.example.com/auth/google/callback`

### Compatibility validation

Before the app initiates Google OAuth, it must validate the derived callback origin.

Allowed:

- `http://localhost:3080`
- `http://127.0.0.1:3080`
- `https://calendar.example.com`

Blocked with operator guidance:

- `http://192.168.50.10:3080`
- `http://calsync.local:3080` unless the operator terminates TLS and uses `https://...`

This validation should happen both:

- in UI rendering, to show the operator what will happen
- at request time, to prevent accidental broken redirect attempts

### `APP_HOST` versus callback origin

`APP_HOST` remains a bind setting only. It must not be treated as the externally advertised callback host. This preserves the Phase 1 rule that binding and public URL generation are separate concerns.

## OAuth Flow Design

### Start route

Add an authenticated admin route such as:

- `GET /auth/google/start`

Responsibilities:

- verify the admin session
- verify Google config presence
- derive the callback URL
- validate redirect compatibility
- generate a cryptographically strong OAuth state value
- store the state in a short-lived server-side session context
- redirect to Google with:
  - `response_type=code`
  - `access_type=offline`
  - `include_granted_scopes=true`
  - the configured scopes
  - `state`

### Consent behavior

Normal connect attempts should request offline access without forcing consent every time. If the app does not receive a refresh token, or if an operator explicitly reconnects an account, the app may retry with `prompt=consent` to refresh the grant intentionally.

This avoids both:

- silently ending up without a refresh token
- showing a forced consent screen on every normal connection

### Callback route

Add an authenticated admin callback route such as:

- `GET /auth/google/callback`

Responsibilities:

- verify the OAuth state
- handle provider error responses cleanly
- exchange the authorization code for tokens
- parse the account identity
- upsert the Google provider account
- encrypt and store token material
- persist granted scopes and token expiry metadata
- trigger immediate calendar discovery
- redirect back to the connected accounts or calendar management UI with a clear success or failure message

### Account identity

Google accounts need a stable external identity and a human-readable label.

Recommended stored fields:

- external account subject or unique Google user id
- primary email address
- display name

These values can live across:

- `provider_account_id`
- `display_name`
- `provider_metadata`

## Persistence Model Changes

The existing provider tables are already close to what Phase 2 needs. This phase extends their usage rather than redesigning them.

### `provider_accounts`

Continue using:

- `provider_type`
- `provider_account_id`
- `display_name`
- `access_token_encrypted`
- `refresh_token_encrypted`
- `provider_metadata`

For Google, `provider_metadata` should carry safe, non-secret fields such as:

- granted scopes
- token expiry timestamp
- account email
- account subject/user id
- last auth status
- reconnect-required flag when refresh fails permanently

### `provider_calendars`

Persist discovered Google calendar metadata such as:

- calendar summary
- time zone
- background color
- access role
- whether Google marked it hidden or selected
- calendar list sync token if stored per account or per discovery context
- events sync token for that calendar

Newly discovered Google calendars should default to disabled until the admin explicitly enables them for aggregation. This matches the product requirement that admins select which calendars to aggregate.

### `sync_logs`

Continue using the existing sync log structure and ensure sanitized error summaries capture Google-specific states such as:

- missing refresh token
- revoked grant
- invalid client configuration
- expired sync token requiring full resync

## Provider Adapter Shape

Phase 2 should preserve the provider adapter pattern introduced in Phase 1, but Google needs a slightly richer interface than the Phase 1 mock.

The Google adapter will need capabilities for:

- account bootstrap after OAuth callback
- calendar discovery
- event fetch
- access-token refresh
- sync token invalidation and full-resync fallback

Rather than spreading Google API calls across routes and services, all Google API interaction should live under:

- `src/calsync/services/providers/google.py`

Any necessary interface extensions should remain generic enough for iCloud to reuse the same sync orchestration later.

## Google Discovery Design

### Discovery endpoint use

Use Google Calendar `calendarList.list` to fetch the authenticated user’s calendar list.

Persist per-calendar metadata needed for the UI:

- calendar id
- summary
- time zone
- color
- primary flag
- access role
- hidden/selected status where available

### Discovery sync token

Store the Google calendar-list sync token so rediscovery can later use incremental updates instead of refetching the entire list every time.

If the token is invalidated, fall back to a full discovery refresh and reconcile calendars again.

## Google Event Sync Design

### Initial full sync

For each enabled Google calendar:

- perform a full `events.list` sync
- preserve event ids, etags, recurrence data, time zone, attendees, reminders, and safe raw payload
- upsert into the existing normalized event repository

### Incremental sync

After a successful full sync:

- store the returned `nextSyncToken`
- reuse it on future syncs

If Google returns `410 Gone`:

- clear the affected calendar sync token
- record a sanitized sync warning
- perform a new full sync for that calendar

### Parameter consistency

Because Google requires stable parameters when using `syncToken`, the implementation should centralize the exact event-list query shape used for full and incremental syncs. The app should not layer ad hoc date filters on top of incremental sync requests.

### Duplicate prevention

Continue using the existing logical uniqueness model:

- provider type
- source account
- source calendar
- provider event id

This must remain idempotent across:

- repeated manual syncs
- worker syncs
- refreshed access tokens
- full resync after token expiration

## Token Refresh And Auth Failure Handling

### Refresh behavior

The sync path should use the stored refresh token to obtain a fresh access token when needed. Updated access tokens and expiry metadata should be persisted without exposing token values in logs.

### Revocation and expiry

If token refresh fails permanently:

- keep the provider account record
- mark the account as needing reconnect
- record a sanitized error in sync status
- do not destroy calendar configuration, groups, events, or ICS feeds

This mirrors the Phase 1 break-glass philosophy: auth problems should not destroy configuration.

## UI Changes

### Connected accounts page

Add a Google section with:

- connect button
- configuration readiness indicator
- callback base URL preview
- redirect compatibility warning when applicable
- connected account list and auth status

### Calendar management page

Display discovered Google calendars alongside the existing provider model, with:

- provider badge
- account label
- calendar name
- enable/disable control
- current auth/sync state where useful

### Sync status page

Expose Google-specific sync information:

- last sync time
- event counts
- auth/reconnect state
- last sanitized error
- manual sync action

### ICS publishing

No separate Google ICS feature is needed. Existing source, group, and combined feed mechanisms should automatically include Google-backed normalized events once the calendars are enabled and synced.

## Worker And Scheduling Impact

Phase 2 reuses the existing worker container and manual sync plumbing.

Immediate requirements:

- worker can sync Google accounts on demand
- manual sync from the admin UI can trigger Google sync safely

Deferred to Phase 4:

- broader retry/backoff policy refinements
- richer scheduling controls
- more advanced status dashboards

## Error Handling

The user experience should clearly distinguish:

- missing Google client configuration
- invalid callback origin for OAuth
- OAuth denial by the user
- invalid or expired authorization code
- missing refresh token after callback
- revoked grant
- calendar discovery failure
- event sync failure
- expired sync token requiring a full resync

Errors must be:

- visible in the admin UI
- sanitized in logs
- stored as concise last-error state when useful

Errors must not log:

- OAuth codes
- access tokens
- refresh tokens
- raw provider responses containing secrets

## Testing Strategy

Phase 2 automated tests should add coverage for:

- Google callback URL generation from `PUBLIC_BASE_URL`
- localhost callback URL generation when `PUBLIC_BASE_URL` is unset
- raw LAN IP callback rejection with a clear operator-facing message
- OAuth state generation and verification
- successful callback handling with mocked Google token/user responses
- callback failure handling when Google returns an error
- missing refresh token handling
- calendar discovery mapping into `provider_calendars`
- event normalization from Google payloads into the local model
- duplicate-safe re-import
- sync token persistence
- `410 Gone` fallback to full resync
- revoked-token/reconnect-required state handling

The suite should run entirely without real Google credentials by mocking Google HTTP responses.

## Documentation Requirements

Phase 2 documentation updates must include:

- `.env.example` entries for Google OAuth configuration
- README instructions for creating a Google OAuth web application client
- exact redirect URI setup examples
- localhost versus LAN callback limitations
- how `PUBLIC_BASE_URL` affects callback generation
- how to reconnect when refresh tokens are missing or revoked
- confirmation that Google access remains read-only

Documentation must reference GitHub issue `#2` as the tracking source for this phase.

## Acceptance Criteria

Phase 2 is accepted when:

- an authenticated admin can start the Google connect flow from the UI
- the app blocks invalid raw-IP callback setups with a clear explanation
- a localhost or HTTPS-hostname callback can complete successfully
- the app stores Google tokens securely and does not log them
- Google calendars are discovered and shown in calendar management
- the admin can enable selected Google calendars for aggregation
- manual or worker sync imports Google events without duplicates
- combined calendar views show Google-backed events
- existing ICS feeds include enabled Google-backed events
- revoked or expired auth is surfaced cleanly without deleting configuration
- tests and docs cover the operator flow and callback constraints

## Recommendation

Implement this as a focused provider slice tied to GitHub issue `#2`, preserving the Phase 1 architecture and explicitly handling Google’s redirect URI limitations instead of hiding them. That keeps the product honest for self-hosted operators and leaves the codebase ready for Phase 3 iCloud CalDAV integration.
