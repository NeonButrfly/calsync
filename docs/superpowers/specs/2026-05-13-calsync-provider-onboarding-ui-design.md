# CalSync Provider Onboarding UI Design

Related GitHub issue: #3

## Summary

CalSync needs a more complete onboarding model than the current Phase 2 Google slice. Operators should be able to configure provider settings through the admin UI, connect multiple Google accounts and multiple Apple/iCloud accounts, and then enable discovered calendars for aggregation. This design replaces the earlier assumption that Google OAuth client credentials remain server-config-only in `.env`.

This is not a per-calendar credential flow. The right mental model is:

- configure provider settings
- connect provider accounts
- discover calendars
- enable calendars for aggregation

## Goals

- Let admins configure deployment-wide Google OAuth app credentials from the web UI.
- Support multiple Google accounts under one configured Google OAuth client.
- Support multiple Apple/iCloud accounts from the web UI using Apple ID and app-specific password.
- Keep provider onboarding read-only.
- Keep credentials encrypted at rest.
- Preserve the existing normalized event store, calendar management, sync, and ICS publishing architecture.
- Make the UI language match the actual model: provider settings, connected accounts, discovered calendars.

## Non-Goals

- No Google write-back.
- No Apple write-back.
- No destructive provider actions.
- No public self-service provider registration.
- No per-calendar credential entry for providers that authenticate at the account level.

## Correct Product Model

### Deployment-wide provider settings

Some provider information belongs to the deployment, not to an individual calendar or account.

For Google, this includes:

- OAuth client ID
- OAuth client secret
- optional scope overrides
- redirect-path configuration where allowed

These values should be stored once per deployment, encrypted at rest where secret material exists, and editable by authenticated admins in the UI.

### Per-account credentials

Some provider information belongs to a specific connected account.

For Apple/iCloud, this includes:

- Apple ID username
- Apple app-specific password

These values are stored per account and are used for account discovery and sync only.

### Discovered calendars

Calendars are children of connected provider accounts. Operators should not manually enter each calendar’s credentials. Instead:

1. Configure provider settings if required.
2. Connect or add an account.
3. Discover calendars from that account.
4. Enable or disable the calendars to aggregate.

## UI Shape

### Provider Settings page

Add an admin page such as:

- `/admin/providers`

This page manages deployment-wide provider configuration.

For Google:

- client ID field
- client secret field
- optional scope field
- callback URL preview
- redirect compatibility guidance
- save action
- last updated metadata

For Apple/iCloud:

- no deployment-wide credentials are needed
- page can instead explain the per-account Apple model and link to add-account actions

### Connected Accounts page

Retain and expand:

- `/admin/accounts`

Capabilities:

- add Google account
- add Apple/iCloud account
- add mock account
- list all connected accounts grouped by provider
- show auth/sync status per account
- reconnect actions when auth breaks

The primary action wording should be:

- `Add account`
- `Connect Google account`
- `Add Apple/iCloud account`

It should not be:

- `Add calendar`

because the calendar is discovered after account connection.

### Calendars page

Retain:

- `/admin/calendars`

But update the empty and guidance text so it clearly points users to connected accounts and discovery, not later roadmap phases.

### Account forms

#### Google

Google account onboarding form is lightweight because the deployment-wide OAuth client is already configured.

Flow:

1. Admin visits provider settings and stores the Google client ID and secret.
2. Admin clicks `Connect Google account`.
3. OAuth starts using the stored deployment-wide client.
4. Returned Google account is added to the connected accounts list.
5. CalSync discovers calendars for that account.

#### Apple/iCloud

Apple onboarding is a real account form because the credentials are per account.

Fields:

- display name or label
- Apple ID email/username
- app-specific password

Behavior:

- validate presence and format as far as reasonable
- encrypt the app-specific password at rest
- attempt CalDAV discovery
- show clear auth failures without deleting the account record unless creation fails entirely

## Persistence Model

## Provider configuration

Add a new durable model for deployment-wide provider settings, for example:

- `provider_configurations`

Suggested fields:

- `id`
- `provider_type`
- `config_key`
- `config_value_encrypted` for secrets
- `config_value_text` for non-secret text
- `created_at`
- `updated_at`

Alternative model:

- one row per provider with encrypted JSON payload

I recommend a row-per-key or row-per-provider JSON model only if it remains easy to audit and rotate. The essential requirement is that Google client secrets are not left only in `.env` once the UI owns them.

### Google account records

Continue using `provider_accounts` for each connected Google account.

Per-account Google fields remain:

- account identity
- display label
- access token
- refresh token
- granted scopes
- reconnect-required state
- sync metadata

### Apple account records

Apple accounts should also use `provider_accounts`, with provider type such as:

- `icloud_caldav`

Per-account Apple fields include:

- account label
- Apple ID username
- encrypted app-specific password
- auth/sync metadata

## Security Model

- Google client secret must be encrypted at rest in the database.
- Apple app-specific passwords must be encrypted at rest in the database.
- Existing admin MFA remains mandatory for all onboarding actions.
- Sensitive provider configuration changes should require normal admin session protection and may later require re-authentication for hardening.
- No secrets are logged.
- Backups now include deployment-wide provider secrets if database backups are taken, so the README and ops docs must reflect that expanded backup sensitivity.

## Behavior Changes From Current Phase 2

### Current behavior

- Google OAuth client ID and secret are read from server configuration.
- Connected accounts page supports mock and Google account onboarding.
- Apple account onboarding is not present.

### New behavior

- Google OAuth client ID and secret become editable from the admin UI.
- The app uses the stored provider configuration when launching Google OAuth.
- The UI explicitly supports multiple Google accounts.
- The UI adds Apple/iCloud account onboarding.
- Empty-state copy across the admin pages must stop referring to “later phases” where the feature is actually present.

## Apple/iCloud Fit

This design also clarifies how Apple lands without bending the model:

- Google uses deployment-wide app credentials plus per-account tokens.
- Apple uses per-account CalDAV credentials directly.
- Both then funnel into discovered calendars and the same enable/disable aggregation model.

## Testing Strategy

Add tests for:

- provider configuration persistence
- encryption and retrieval of stored Google client secret
- provider settings page rendering and save behavior
- Google connect flow when credentials are stored in the database instead of `.env`
- connected accounts page showing multiple Google accounts
- Apple add-account form validation
- Apple discovery handling in mock or provider-test mode
- calendars page empty-state guidance

## Documentation Requirements

Update:

- `README.md`
- `docs/ops.md`
- `docs/prompts/backend.md`

To reflect:

- UI-managed Google provider configuration
- multiple provider accounts
- Apple per-account onboarding
- secret storage implications for database backups

## Recommendation

Implement issue `#3` as a new onboarding layer on top of the current Phase 2 foundation. Keep the existing Google OAuth sync logic, but move Google client credentials into admin-managed provider configuration and add a first-class multi-account onboarding model that Apple can share.
