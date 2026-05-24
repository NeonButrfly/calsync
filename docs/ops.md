# CalSync Operations

## Docker Bring-Up

1. Copy `.env.example` to `.env`
2. Set `SESSION_SECRET` and `ENCRYPTION_KEY`
3. Review `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, and the provider onboarding plan for Google and Apple accounts
4. Run `docker compose up --build`

For local rebuilds:

```bash
docker compose up --build
```

For detached startup:

```bash
docker compose up --build -d
docker compose ps
```

The long-running `db`, `web`, and `worker` services use `restart: unless-stopped`, so a normal host reboot or Docker daemon restart should bring the stack back without a manual `docker compose up -d`.

## Google OAuth Operator Notes

Before connecting Google from a non-local browser, open `Provider Settings` and save the canonical external hostname in `Public App URL`.

Deployment example:

- `https://calsync.neonbutterfly.net`

Set these values in `.env` only if you want bootstrap fallback credentials before signing in to the admin UI:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- optional `GOOGLE_OAUTH_SCOPES`
- optional `GOOGLE_OAUTH_REDIRECT_PATH`

Normal operator flow:

1. sign in to CalSync
2. open `/admin/providers`
3. save the `Public App URL` there when the deployment should use a stable HTTPS hostname
4. save the shared Google OAuth client ID and secret there
5. confirm the callback URL shown on the page matches the saved public hostname when present
6. open `/admin/accounts`
7. use `Connect Google Account`
8. connect one or more Google accounts

Google Cloud setup checklist for multiple accounts:

1. create or choose one Google Cloud project for this CalSync deployment
2. enable the Google Calendar API
3. open `Google Auth Platform`
4. complete `Branding` with app name, support email, and contact email
5. choose the right `Audience`
   - use `External` for personal Gmail accounts or a mix of Google accounts
   - use `Internal` only when all accounts belong to the same Google Workspace organization
6. if the app is `External` and still in testing mode, add every Google account you want to connect under `Test users`
7. in `Data Access`, add:
   - `openid`
   - `email`
   - `profile`
   - `https://www.googleapis.com/auth/calendar.readonly`
8. in `Clients`, create a `Web application` OAuth client
9. add the redirect URI shown by CalSync on `/admin/providers`
10. paste that client ID and client secret into CalSync once, then connect each Google account separately from `/admin/accounts`

Operational note:

- one Google OAuth web client is enough for multiple connected Google accounts in the same CalSync deployment
- each Google account still has to complete its own consent flow
- if Google shows a testing or unverified-app restriction, check the Google Auth Platform `Audience` and `Test users` settings first
- after you explicitly enable Google calendars in `/admin/calendars`, later incremental sync cycles should preserve those enabled selections instead of turning them off again when Google reports no calendar-list changes

Redirect URI examples:

- `http://localhost:3080/auth/google/callback`
- `https://calendar.example.com/auth/google/callback`

Important limitation:

- Google does not accept raw LAN IP callback URIs such as `http://192.168.50.232:3080/auth/google/callback`

If operators need to connect Google from another device on the LAN, they should set `PUBLIC_BASE_URL` to an HTTPS hostname or domain that is registered in Google Cloud.

In the admin-managed flow, saving `Public App URL` in `/admin/providers` is the preferred way to do this because the Accounts page will then use that saved hostname for the Google callback and consent start.

## Flightboard Operator Notes

The private Flightboard is available at:

- `/admin/flightboard`

Behavior:

- requires an authenticated admin session
- shows only current and upcoming enabled calendar events
- offers `Day`, `Week`, and `Month` range controls inside the page
- converts UTC-backed event displays into Alaska local time with a consistent `AKST` label
- keeps the column header fixed above the rows instead of letting it overlap event content
- provides an explicit auto-scroll toggle and remembers that preference in the browser
- scrolls automatically for unattended viewing and pauses on hover
- duplicates visible rows client-side when needed so shorter schedules still auto-scroll instead of appearing static
- is intended for private operations viewing, not anonymous public display

Practical verification points:

- the top navigation includes `Flightboard`
- opening `/admin/flightboard` after login renders the private board
- the board excludes events whose end time has already passed
- UTC-backed event times render in Alaska time instead of showing raw UTC labels
- the selected range changes which upcoming events are shown
- unauthenticated access should redirect to login instead of exposing events

Dashboard and sync-status timestamps should follow the same Alaska display convention.

## Connections And Calendar Roles

The scheduling-product shell now routes account onboarding through:

- `/admin/accounts` as `Connections`
- `/admin/calendars` as `Availability`

Operator expectations for this slice:

- Google uses the existing browser-based OAuth connect flow when Provider Settings and callback requirements are satisfied
- Apple keeps the current CalDAV plus app-specific-password form
- existing Apple connector rows and encrypted app-specific passwords are preserved while the surrounding shell and tables are refreshed
- Microsoft is visible in the Connections page so the product IA matches the write-capable direction
- `/admin/providers` now stores the shared Microsoft OAuth app fields and shows the planned callback URL for the future Outlook connect flow
- the page is intentionally honest that Microsoft sign-in and calendar permissions are not shipped yet
- full booking pages are not shipped in this slice

Calendar role behavior:

- `Check availability` means a calendar contributes busy-time and availability signal
- `Receive new bookings` means the calendar is a writable booking target
- writable booking target is only valid for a writable provider account and writable calendar
- read-only connections should continue to offer availability-only behavior instead of pretending booking writes will work

Practical verification points:

- the top navigation includes `Connections` and `Availability`
- `/admin/accounts` shows Google Calendar, Outlook / Microsoft 365, Apple Calendar, and Mock Provider
- the Microsoft card starts by saying `Microsoft sign-in and calendar permissions` are still coming next, then changes to a saved-state scaffold message after the shared Microsoft app is stored
- `/admin/providers` shows `Microsoft OAuth App` and a planned callback URL without claiming the Outlook account connection flow is already live
- `/admin/calendars` shows `Check availability` for connected calendars
- `/admin/calendars` only shows `Receive new bookings` when the provider account supports writable booking targets
- existing Apple/iCloud accounts remain visible in the connected-accounts table after the shell refresh

## Trust Review Operator Notes

The trust review page is available at:

- `/admin/review`

Behavior:

- requires an authenticated admin session
- groups obvious duplicate appointments using conservative near-match rules, including small title drift and small time drift
- shows which copy CalSync currently prefers
- lets the operator choose `Keep this copy` when the same appointment was added twice
- lets the operator restore a hidden duplicate if both copies should stay visible
- keeps hidden-duplicate decisions across later sync refreshes
- removes events from active views when the upstream provider cancels them, deletes them, or removes their calendar during a full discovery pass
- surfaces a `Needs attention` queue so duplicate cleanup is easier to find during normal admin use

Practical verification points:

- the top navigation includes `Review`
- the dashboard shows a `Trust review` summary card
- the dashboard combined calendar collapses duplicate copies into one row and shows a multi-source badge when more than one provider copy exists
- `/admin/review` shows `Needs attention` and `Possible duplicates` when matching copies exist
- choosing `Keep this copy` hides the extra copy from active dashboard, flightboard, and ICS surfaces
- restoring a hidden duplicate should keep that copy visible even after the page recalculates duplicate groups
- if a calendar disappears from provider discovery, its old events become `deleted_upstream` instead of staying active forever

## Problem To Fix Inbox

The operator problem inbox is available at:

- `/admin/problems`

Behavior:

- gathers duplicate cleanup, sync retry, and account authentication problems into one list
- sorts higher-risk sync and auth items ahead of lower-risk cleanup items
- offers the safest next action for each problem, such as `Review duplicates`, `Keep Google copy`, `Keep iCloud copy`, `Show all copies`, `Explain this event`, `Sync now`, or `Reconnect in accounts`
- returns `Sync now` actions back to the problem inbox so the operator can keep working from one page

Practical verification points:

- the top navigation includes `Problems`
- the dashboard shows a `Problems to fix` summary card
- `/admin/problems` shows `Problem to fix list`
- duplicate items link into `/admin/review`
- duplicate items also provide `Explain this event` links into `/admin/events/{event_id}`
- sync retry items can run directly from the inbox and redirect back to `/admin/problems`

## Event Explain View

The event explain page is available at:

- `/admin/events/{event_id}`

Behavior:

- requires an authenticated admin session
- explains why the selected appointment copy is preferred, hidden, or still visible
- lists the grouped source copies that belong to the same duplicate cluster
- shows the latest sync status for the owning provider account when available

Practical verification points:

- opening `/admin/events/{event_id}` after login renders `Why CalSync is showing this appointment`
- the page shows `Grouped source copies`
- the page marks the preferred copy clearly
- unauthenticated access should redirect to login instead of exposing appointment details

## Apple / iCloud Operator Notes

Apple/iCloud onboarding is account-based, not deployment-based.

For each Apple account:

1. open `/admin/accounts`
2. enter an account label
3. enter the Apple ID username or email
4. enter an app-specific password
5. submit the form to discover calendars

The Apple credentials are encrypted at rest in the CalSync database.
The write-capable redesign foundation keeps existing Apple connector rows and stored app-specific passwords in place instead of replacing them with a fake Apple OAuth path.

## Backup

Back up the database with:

```bash
docker compose exec db pg_dump -U calsync -d calsync > calsync-backup.sql
```

Back up configuration with:

```bash
cp .env .env.backup
```

Recommended backup set:

- PostgreSQL dump
- `.env`
- encrypted Google provider settings and encrypted Apple app-specific passwords inside the CalSync database
- any local deployment notes or Compose overrides

## Restore

Restore the database with:

```bash
docker compose exec -T db psql -U calsync -d calsync < calsync-backup.sql
```

Then restore `.env` and restart:

```bash
docker compose up --build
```

## Health Checks

The web service exposes:

- `GET /healthz`

Expected local check:

```bash
curl http://localhost:3080/healthz
```

Public-host check example:

```bash
curl -sS https://calsync.neonbutterfly.net/healthz
```

## Deployment Verification Checklist

After `docker compose up --build -d`, verify:

1. `docker compose ps` shows healthy `web`, `worker`, and `db` containers
2. the health endpoint returns `ok`
3. `/admin/providers` shows or supports `Public App URL` with `https://calsync.neonbutterfly.net`
4. `/admin/accounts` shows `Connect Google Account` once Google settings and public hostname requirements are satisfied
5. `/admin/flightboard` is present in the nav and remains private behind admin auth
6. `/admin/accounts` presents the brighter `Connections` framing and an honest Microsoft scaffold state
7. `/admin/calendars` exposes `Check availability`, and only writable provider accounts can be assigned `Receive new bookings`

Reboot recovery check:

1. after a host reboot or Docker restart, run `docker compose ps`
2. confirm `db`, `web`, and `worker` return automatically
3. confirm `GET /healthz` returns `ok`
4. if the stack was intentionally stopped with `docker compose down` or `docker compose stop`, bring it back with `docker compose up -d`

## Local Emergency Procedures

Reset an admin password without destroying configuration:

```bash
docker compose exec web python -m calsync.cli reset-admin-password --identifier admin
```

Reset admin MFA and issue fresh recovery codes:

```bash
docker compose exec web python -m calsync.cli reset-admin-mfa --identifier admin
```

These commands preserve provider accounts, calendar selections, feed tokens, and sync state.

## Worker Notes

The worker uses the same database and settings as the web service and polls on the configured `SYNC_POLL_SECONDS` interval.

Current Phase 1 behavior:

- discovers and syncs any stored provider accounts
- records sync results in the database
- survives container restarts because state is persisted in PostgreSQL

Current Phase 2 addition:

- refreshes and syncs Google provider accounts through the same worker loop
- refreshes and syncs Apple/iCloud CalDAV accounts through the same worker loop
