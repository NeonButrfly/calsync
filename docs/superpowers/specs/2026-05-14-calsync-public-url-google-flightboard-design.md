# CalSync Public URL, Google Connect, and Flightboard Design

- Date: 2026-05-14
- GitHub issue: `#4`
- Related issues: `#2`, `#3`
- Status: Proposed

## Overview

CalSync already supports provider onboarding, Google OAuth, and private admin pages, but the current operator experience still assumes that the browser host used for sign-in is also the best host for external URL generation. That works for `localhost`, but it breaks down when the app is self-hosted on a LAN IP and exposed publicly through a real HTTPS hostname.

This design adds a deployment-level public URL setting that admins can manage in the UI, uses that saved URL as the preferred external origin for Google OAuth and generated feed links, and introduces a private flightboard-style event view for enabled calendars.

The target public hostname for the first real deployment is:

- `https://calsync.neonbutterfly.net`

## Goals

- Let admins save and update a canonical public app URL from the admin UI.
- Prefer the saved public URL for generated external links.
- Unblock Google account connection when the saved public URL is a Google-compatible HTTPS hostname.
- Make the Accounts page explain exactly which callback host Google will use.
- Add a private admin-only scrolling flightboard-style view for enabled calendars.
- Preserve existing LAN and localhost usability for normal admin browsing.

## Non-Goals

- No public anonymous flightboard view in this phase.
- No change to the read-only provider boundary.
- No reverse proxy or certificate automation work inside CalSync itself.
- No multi-URL routing matrix beyond one canonical public URL plus normal request-host fallback.

## Current Problem

Today the app can render Google OAuth settings, but the Accounts page hides the Google connect action when the active request host is not valid for Google OAuth. On a self-hosted deployment, that means browsing from a LAN IP can suppress Google onboarding even when the deployment already has a valid public HTTPS hostname available.

At the same time, CalSync does not yet expose a general admin-managed public app URL in the UI, and the calendar area only offers management-style list views instead of an operational display view.

## Proposed Approach

### 1. Admin-Managed Public Base URL

Add a deployment-level setting in the admin UI for the canonical public app URL.

Expected behavior:

- The setting is stored in the database and survives restart.
- The setting is editable from the Provider Settings page or a closely related app settings page.
- The stored URL must be normalized and validated.
- The value should allow standard HTTPS hostnames such as `https://calsync.neonbutterfly.net`.
- HTTP should still be allowed for local development only when explicitly used as a non-Google local value, but the UI should guide operators toward HTTPS for public use.

This setting becomes the canonical origin for:

- Google callback preview and compatibility checks
- generated ICS links intended for external subscription
- future provider callback previews that require a public hostname

### 2. URL Resolution Rules

CalSync should use a simple precedence model:

1. For Google OAuth callback generation:
   - prefer the saved public URL when it is present and valid for Google OAuth
   - otherwise fall back to the current request origin if that origin is valid
   - otherwise block the connect flow and explain why
2. For public feed and externally shared links:
   - prefer the saved public URL when present
   - otherwise fall back to the current request origin
3. For internal admin navigation:
   - continue using normal relative app routes

This keeps external URL generation stable without forcing operators to browse through the public hostname for every admin task.

### 3. Google Connect Behavior

Once a valid public HTTPS hostname is saved, the Accounts page should expose the Google connect action even if the admin is currently browsing from:

- `http://192.168.x.x:3080`
- `http://localhost:3080`
- another non-public local origin

The page should explicitly communicate:

- the callback URL Google will use
- whether the saved public URL is valid for Google OAuth
- why the button is unavailable when it is still blocked

Example operator copy:

- `Google sign-in will use https://calsync.neonbutterfly.net/auth/google/callback`

The goal is to remove ambiguity. If Google is blocked, the UI should tell the operator whether the problem is:

- missing client credentials
- missing public URL
- non-HTTPS hostname
- raw IP callback

### 4. Provider Settings UX

The Provider Settings area should evolve from a Google-only credentials form into a broader deployment settings page for provider-facing URL and auth configuration.

Recommended layout:

- `Public App URL`
  - canonical HTTPS hostname for shared links and OAuth callbacks
- `Google OAuth App`
  - client ID
  - client secret
  - scopes
  - callback preview
  - source indicator

This still keeps Apple onboarding on the Accounts page, since Apple credentials are per account rather than deployment-wide.

### 5. Private Flightboard View

Add a new admin-only route and template for a scrolling flightboard-style event board.

Characteristics:

- only visible to authenticated admins
- driven entirely from the normalized local event store
- shows events from enabled calendars only
- optimized for continuous passive viewing
- readable from a distance
- auto-refreshes or auto-advances without manual interaction

Recommended data shown per row:

- start time
- end time or duration
- event title
- source calendar name
- location when present
- relative status such as `Now`, `Soon`, or upcoming time

Recommended display behavior:

- sort by start time
- include only near-future and in-progress events within a configurable window
- continuously scroll or cycle through rows
- use a high-contrast board-style layout rather than the existing admin table style

This view should be available from the main admin navigation as a separate destination, not mixed into the calendar-management page.

## Data Model Changes

Minimal schema expansion is preferred.

Add deployment-level app settings entries for:

- `public_base_url`

Existing Google provider settings storage can remain in place.

No new provider-account schema is required for this phase.

The flightboard view should not require new persistent tables in the first version; it can query enabled calendars and upcoming normalized events directly.

## Security and Access

- The public app URL setting remains admin-only.
- The flightboard view remains admin-only.
- Google OAuth still uses encrypted secret storage and read-only scopes unless explicitly broadened by the operator.
- No new public tokens are introduced for the flightboard view.

## Error Handling

The UI should distinguish between:

- `Google not configured`
- `Google configured but callback host invalid`
- `Public URL saved but not HTTPS`
- `Public URL missing`
- `Current request host is not valid, but saved public URL is valid`

The ideal result is that the operator always understands the next step without needing server logs.

## Testing Plan

Add or update tests for:

- saving the public app URL from the admin UI
- URL generation precedence between saved public URL and request origin
- Google connect availability when the saved public URL is valid
- Google block messaging when the saved public URL is missing or invalid
- accounts page callback-host messaging
- flightboard route authentication
- flightboard rendering using enabled calendars only
- flightboard event ordering and filtering

Deployment verification should include:

- Pi deployment with `https://calsync.neonbutterfly.net` saved as the public URL
- Accounts page showing Google connect
- callback preview using the saved hostname
- flightboard page reachable after admin login

## Rollout Notes

This work should be tracked as issue `#4`, with issue `#2` remaining the Google integration foundation and issue `#3` remaining the broader provider onboarding umbrella.

Implementation should stay incremental:

1. public URL setting and URL precedence
2. Google connect unblock and operator messaging
3. private flightboard route, query, template, and nav link

