# CalSync Operations

## Docker Bring-Up

1. Copy `.env.example` to `.env`
2. Set `SESSION_SECRET` and `ENCRYPTION_KEY`
3. Review `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, and the provider onboarding plan for Google, Microsoft, and Apple accounts
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
   - `https://www.googleapis.com/auth/calendar`
8. in `Clients`, create a `Web application` OAuth client
9. add the redirect URI shown by CalSync on `/admin/providers`
10. paste that client ID and client secret into CalSync once, then connect each Google account separately from `/admin/accounts`

Operational note:

- one Google OAuth web client is enough for multiple connected Google accounts in the same CalSync deployment
- each Google account still has to complete its own consent flow
- if Google shows a testing or unverified-app restriction, check the Google Auth Platform `Audience` and `Test users` settings first
- after you explicitly enable Google calendars in `/admin/calendars`, later incremental sync cycles should preserve those enabled selections instead of turning them off again when Google reports no calendar-list changes
- reconnecting an existing Google account now clears stale Google incremental sync tokens and falls back to a full calendar discovery so the callback does not fail on old sync state
- if Google grants only identity scopes and not calendar access, CalSync should return a friendly reconnect error instead of a raw internal server error

Redirect URI examples:

- `http://localhost:3080/auth/google/callback`
- `https://calendar.example.com/auth/google/callback`

Important limitation:

- Google does not accept raw LAN IP callback URIs such as `http://192.168.50.232:3080/auth/google/callback`

If operators need to connect Google from another device on the LAN, they should set `PUBLIC_BASE_URL` to an HTTPS hostname or domain that is registered in Google Cloud.

In the admin-managed flow, saving `Public App URL` in `/admin/providers` is the preferred way to do this because the Accounts page will then use that saved hostname for the Google callback and consent start.

## Microsoft OAuth Operator Notes

Before connecting Outlook / Microsoft 365 from a browser, open `Provider Settings` and save the canonical external hostname in `Public App URL` when the deployment should use a stable HTTPS hostname.

Set these values in `Provider Settings` for the shared Microsoft OAuth app:

- client ID
- client secret
- scopes

Normal operator flow:

1. sign in to CalSync
2. open `/admin/providers`
3. save the `Public App URL` there when the deployment should use a stable HTTPS hostname
4. save the shared Microsoft OAuth client ID and secret there
5. confirm the callback URL shown on the page matches the saved public hostname when present
6. open `/admin/accounts`
7. use `Connect Microsoft Account`
8. complete Outlook / Microsoft 365 consent for one or more accounts
9. open `/admin/calendars`
10. enable the discovered Microsoft calendars that should participate in availability or future booking selection

Operational note:

- one Microsoft OAuth app is enough for multiple connected Outlook / Microsoft 365 accounts in the same CalSync deployment
- each Microsoft account still has to complete its own consent flow
- Microsoft calendar discovery is live after account connection, with discovered calendars disabled by default until the operator enables them
- Microsoft sync is read-only in this slice and imports events into the normalized local event store
- provider write-back is not shipped yet and remains future work under issue `#23`

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
- Microsoft uses a live browser-based OAuth account-connect flow for Outlook / Microsoft 365 accounts
- `/admin/providers` stores the shared Microsoft OAuth app fields and shows the active callback URL for that connect flow
- connected Microsoft accounts can discover calendars and sync read-only events into the normalized local event store
- full booking pages are not shipped in this slice
- `/admin/appointments/new` now creates appointments on writable Google and Apple/iCloud calendars that are marked `Receive new bookings`
- `/admin/events/{event_id}` now shows `Edit appointment` and `Cancel appointment` when the owning source calendar is writable

Calendar role behavior:

- `Check availability` means a calendar contributes busy-time and availability signal
- `Receive new bookings` means the calendar is a writable booking target
- writable booking target is only valid for a writable provider account and writable calendar
- read-only connections should continue to offer availability-only behavior instead of pretending booking writes will work

Practical verification points:

- the top navigation includes `Connections` and `Availability`
- the product shell now uses a persistent left sidebar instead of a row of navigation tiles
- the sidebar navigation scrolls independently, and the old top-right quick-link chip bar is intentionally removed to avoid duplicate navigation patterns
- `/admin/accounts` shows Google Calendar, Outlook / Microsoft 365, Apple Calendar, and Mock Provider
- `/admin/accounts` offers `Connect Microsoft Account` once the shared Microsoft OAuth app is configured
- `/admin/providers` shows `Microsoft OAuth App` and the active callback URL for the Outlook account connection flow
- connected Microsoft accounts can discover calendars and then sync read-only events after the operator enables the desired calendars
- `/admin/calendars` shows `Check availability` for connected calendars
- `/admin/calendars` shows inline helper text and select tooltips explaining what each calendar role means
- `/admin/calendars` keeps the role explainer in a `Purpose guide` side panel rather than repeating it as a row of little cards above the table
- `/admin/calendars` now groups each connected account in a collapsible section with enabled-count chips so large calendar inventories stay easier to scan
- raw account and calendar identifiers are tucked behind `Show source details` disclosures instead of always rendering inline
- `/admin/calendars` only shows `Receive new bookings` when the provider account supports writable booking targets
- if the shell layout looks wrong after a deploy, confirm the browser picked up the cache-busted `app.css?v=...` URL instead of an older stylesheet
- existing Apple/iCloud accounts remain visible in the connected-accounts table after the shell refresh

## Trust Review Operator Notes

The trust review page is available at:

- `/admin/review`

Behavior:

- requires an authenticated admin session
- groups obvious duplicate appointments using conservative near-match rules, including small title drift and small time drift
- shows which copy CalSync currently prefers
- names the exact provider, account, and calendar copy in keep actions instead of only saying `Keep this copy`
- event explain now leads with a `Current recommendation` callout and moves low-level provider identifiers into a dedicated disclosure
- lets the operator restore a hidden duplicate if both copies should stay visible
- keeps hidden-duplicate decisions across later sync refreshes
- removes events from active views when the upstream provider cancels them, deletes them, or removes their calendar during a full discovery pass
- surfaces a `Needs attention` queue so duplicate cleanup is easier to find during normal admin use

Practical verification points:

- the top navigation includes `Review`
- the dashboard shows a `Trust review` summary card
- the dashboard combined calendar collapses duplicate copies into one row and shows a multi-source badge when more than one provider copy exists
- `/admin/review` shows `Needs attention` and `Possible duplicates` when matching copies exist
- `/admin/review` explains why the grouped copies look duplicated and which copy CalSync is currently keeping visible
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
- duplicate items explain which copy CalSync currently recommends keeping
- duplicate items show which exact account and calendar copy CalSync currently recommends keeping and which connected sources are involved
- stale historical duplicates stay in the local reference store, but the active inbox ignores old lookback noise outside the current attention window
- trust-facing dates show the year whenever an item is not from the current year
- trust-facing problem and review timestamps now always include the year so historical cleanup never looks like current-year ambiguity
- the dashboard `Upcoming schedule` view also ignores stale long-running leftovers whose start dates are far behind the present, even if a bad source record still carries a future end time
- returns `Sync now` actions back to the problem inbox so the operator can keep working from one page

Practical verification points:

- the top navigation includes `Problems`
- the dashboard shows a `Problems to fix` summary card
- `/admin/problems` is the private problem to fix list
- `/admin/problems` shows `Fix what needs attention`
- duplicate items link into `/admin/review`
- duplicate items also provide `Explain this event` links into `/admin/events/{event_id}`
- writable event detail pages let operators jump directly into `Edit appointment` or `Cancel appointment`
- sync retry items can run directly from the inbox and redirect back to `/admin/problems`

## Auth Experience

The private admin auth flow now uses the same visual system as the main product shell.

Behavior:

- `/login` renders a centered card-based sign-in experience
- the primary path remains username or email plus password
- standard admin accounts continue into `/login/mfa` after the password step
- a designated break-glass admin created through `ensure-break-glass-admin` can establish an admin session after the password step alone
- the page also shows planned invited-user social sign-in options for Google, Microsoft, Apple, and Facebook without implying those identity providers are live for CalSync user auth yet
- `/login/mfa` renders the second-factor challenge in the same card-based layout

Practical verification points:

- `/login` renders `Welcome back`
- `/login` includes `Continue with Google`, `Continue with Microsoft`, `Continue with Apple`, and `Continue with Facebook`
- `/login/mfa` renders `Two-step verification`

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
- writable source copies expose `Edit appointment` and `Cancel appointment`
- unauthenticated access should redirect to login instead of exposing appointment details

## Writable Appointment Editor

The first writable appointment editor is available at:

- `/admin/appointments/new`

Behavior:

- requires an authenticated admin session
- only lists calendars that are enabled, marked `Receive new bookings`, and actually support write-back
- creates appointments on writable Google and Apple/iCloud calendars
- edits and cancels appointments from `/admin/events/{event_id}` when that source calendar is writable
- keeps the normalized local event store and trust graph in sync after create, edit, and cancel actions
- Microsoft stays read-only in this slice and should not appear as a writable target

Practical verification points:

- `/admin/appointments/new` renders `Create appointment`
- writable Google and Apple/iCloud calendars appear as target choices
- saving a new appointment redirects to `/admin/events/{event_id}`
- editing a writable event pre-fills the existing title, location, and times
- cancelling a writable event removes it from active schedule views or marks it cancelled locally

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
6. `/admin/accounts` presents the brighter `Connections` framing and offers `Connect Microsoft Account` after the shared Microsoft OAuth app is configured
7. `/admin/calendars` exposes `Check availability`, and only writable provider accounts can be assigned `Receive new bookings`
8. Microsoft callback registration, account connection, calendar discovery, and read-only sync all work without implying write-back support

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

Create or refresh a controlled break-glass admin account:

```bash
docker compose exec web python -m calsync.cli ensure-break-glass-admin --username browser-admin --email browser-admin@example.com
```

The break-glass admin is explicitly MFA-exempt after the password step. Use it only for local operator recovery or rendered browser verification when the normal MFA-backed admin flow would block automated QA.

## Worker Notes

The worker uses the same database and settings as the web service and polls on the configured `SYNC_POLL_SECONDS` interval.

Current Phase 1 behavior:

- discovers and syncs any stored provider accounts
- records sync results in the database
- survives container restarts because state is persisted in PostgreSQL

Current Phase 2 addition:

- refreshes and syncs Google provider accounts through the same worker loop
- refreshes and syncs Microsoft provider accounts through the same worker loop
- refreshes and syncs Apple/iCloud CalDAV accounts through the same worker loop
