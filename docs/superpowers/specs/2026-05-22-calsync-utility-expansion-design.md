# CalSync Utility Expansion Design

## Metadata

- Date: 2026-05-22
- Canonical issue: `#11`
- Scope: turn CalSync from a basic read-only calendar aggregator into a more trustworthy personal scheduling utility through sync hygiene, duplicate resolution, richer event lifecycle handling, and extensible appointment ingestion

## Goals

- make connected calendars more trustworthy as a day-to-day utility
- remove stale or deleted upstream events from the local normalized store
- reduce duplicate or near-duplicate appointments across multiple providers
- preserve source provenance while presenting cleaner canonical events to the operator
- introduce a safe ingestion adapter framework for appointment sources beyond standard calendar providers
- create a path for portal and message-derived appointment ingestion without weakening provider security or CalSync's read-only posture

## Non-Goals

- no bidirectional write-back to Google, Apple, portals, or messaging systems
- no destructive upstream actions
- no promise of generic browser scraping against arbitrary patient portals
- no claim that iCloud phone backups can be safely or reliably ingested server-side as a first-class source
- no attempt to solve every external appointment source in a single implementation pass

## Product Problem

CalSync already connects multiple Google and Apple/iCloud accounts, syncs events into a local normalized store, and provides admin views plus ICS exports. That foundation is useful, but it still behaves like an aggregator rather than a trusted scheduling utility.

The operator now wants CalSync to feel dependable:

- connected calendars should stay current
- removed or obsolete upstream items should disappear locally
- duplicate entries across providers should be resolved instead of cluttering the schedule
- the system should be extensible enough to pull in appointments from non-calendar systems when feasible

## Constraints And Reality Boundaries

### Calendar trust first

The highest-value immediate work is not adding the hardest new source first. It is making the current event graph trustworthy:

- lifecycle reconciliation for deleted or cancelled upstream events
- duplicate and near-duplicate clustering
- canonical presentation of a real-world appointment even when multiple sources mention it

### Athena patient portal

Athena-style patient portal integration should be treated as an adapter candidate, not a guaranteed generic login feature. The likely viable path is a registered OAuth and FHIR-style integration, not arbitrary scraping of any portal with saved credentials.

That means CalSync should prepare a provider and source-hook architecture now, but the real Athena connector should be gated behind a feasibility pass against the operator's actual portal and permitted auth flow.

### iCloud phone backups and SMS

Server-side ingestion from iCloud phone backups is not an appropriate first-class integration target:

- iCloud backups are protected and not designed as a normal server-side app ingestion surface
- message data availability depends on the operator's Apple sync and backup configuration
- using backups as the system-of-record source would create a brittle and privacy-heavy path

Instead, CalSync should support message-derived appointment ingestion through safer future inputs:

- operator-supplied exports
- device-local extraction tools that produce importable normalized artifacts
- email or message reminder parsers where the data can be accessed legitimately and repeatably

## Recommended Architecture

### 1. Event Trust Layer

This becomes the core reliability system on top of the existing normalized event store.

Responsibilities:

- track upstream event lifecycle states such as active, cancelled, deleted, stale, and superseded
- remove or hide events that no longer exist upstream
- compare events across providers to detect obvious duplicates and probable duplicates
- create canonical event groupings so the UI can show one appointment with multiple source records behind it
- assign source confidence and preferred-source policy when duplicate candidates conflict

New concepts:

- `event_instance`: the existing provider-backed event row
- `event_group`: a canonical real-world appointment grouping
- `event_link_reason`: why two items were grouped, such as exact UID match, same title/time, or imported reminder match
- `event_visibility_state`: active, hidden_duplicate, cancelled, deleted_upstream, stale_unverified

### 2. Source Adapter Layer

CalSync should continue treating Google and iCloud as structured providers, but it now also needs a more general ingestion contract for other appointment sources.

Adapter families:

- `calendar_provider`: Google, iCloud, future CalDAV or ICS-backed sources
- `structured_appointment_source`: FHIR or portal-backed appointment APIs
- `derived_signal_source`: email-derived or message-derived appointment hints
- `import_source`: uploaded export or locally produced appointment artifacts

Adapter contract expectations:

- discovery or source-registration flow
- source-level auth and credential storage rules
- fetch normalized appointment candidates
- attach source provenance and confidence metadata
- never write upstream

### 3. Reconciliation Policy Layer

The operator will need clear, deterministic behavior when sources disagree.

Policy examples:

- prefer Google over derived reminder when both describe the same appointment
- keep portal reminder details but suppress it from the primary calendar view if a confirmed provider event already exists
- keep cancelled items available in source history but hide them from active schedule views
- mark ambiguous duplicates for review instead of silently collapsing them

### 4. Review And Control Layer

CalSync should expose utility-grade controls instead of only passive sync.

Planned operator surfaces:

- duplicate review queue
- stale event cleanup summary
- source trust and reconciliation policy settings
- manual unmerge or merge actions for problematic clusters
- source health and last-seen reporting for new appointment adapters

## Data Model Changes

### Existing tables to extend

- `events`
  - add lifecycle status fields
  - add soft-delete or upstream-removed markers
  - add last-seen-upstream and reconciliation metadata
  - preserve raw source payload where safe

### New tables

- `event_groups`
  - canonical group id
  - display title
  - preferred start and end
  - preferred location
  - preferred source event id
  - confidence summary

- `event_group_members`
  - event id
  - group id
  - role such as canonical, duplicate, reminder, or derived_hint
  - grouping reason

- `source_adapters`
  - type
  - label
  - auth mode
  - status
  - encrypted credentials where applicable

- `source_sync_state`
  - adapter id
  - last sync time
  - last successful cursor or checkpoint
  - last error
  - stale threshold markers

- `event_reviews`
  - review type
  - target event or group
  - status
  - operator note

## UX Direction

### Admin Dashboard

Add trust-oriented summary cards:

- stale items pending cleanup
- duplicate groups requiring review
- source health warnings
- new appointment-source connectors available

### Calendar Views

Default to canonical grouped events rather than every raw provider event, while still allowing drill-down into source members.

### Sync Status

Show:

- last successful upstream confirmation per source
- deleted or cancelled item counts
- duplicate-group creation counts
- source-level errors for non-calendar adapters

### New Sources

Rename the relevant admin area conceptually from only `Connected Accounts` to a broader source model over time:

- connected calendar accounts
- connected appointment sources
- import sources

This should be introduced carefully so existing Google and iCloud flows remain familiar.

## Phased Delivery

### Phase A: Trust And Cleanup Foundation

Highest-value immediate slice.

Deliver:

- upstream deletion and cancellation reconciliation
- local stale-event cleanup behavior
- duplicate detection foundation
- canonical grouped display model
- tests around cleanup and duplicate suppression

Outcome:

The app becomes meaningfully more dependable even before new source types land.

### Phase B: Generalized Appointment Ingestion Framework

Deliver:

- adapter interfaces for non-calendar appointment sources
- source registration model
- source sync state and health reporting
- import-friendly normalized appointment ingestion path

Outcome:

CalSync can ingest appointment-like records from more than just Google and iCloud.

### Phase C: Safer Derived Appointment Sources

Deliver:

- import or parser flow for operator-supplied appointment reminder artifacts
- possibly email-derived appointment extraction if the user wants that later
- conservative duplicate reconciliation into canonical event groups

Outcome:

Reminder-style data can enrich the schedule without becoming a destructive or authoritative source.

### Phase D: Athena Feasibility Connector

Deliver only if viable:

- a dedicated Athena-style source adapter
- operator configuration UI
- OAuth or registered-app flow consistent with the real portal capabilities
- read-only appointment import into canonical groups

Outcome:

Portal-backed appointments become an additional trusted source when the required auth path is actually supported.

## First Implementation Recommendation

The next implementation plan should target `Phase A`.

Why:

- it improves the value of every existing calendar immediately
- it reduces clutter and confusion before adding more data sources
- it creates the event lifecycle and canonical grouping primitives that later adapters will need anyway

First concrete deliverables:

- mark upstream-missing or deleted events locally
- stop showing cancelled or deleted items as normal active events
- detect duplicate candidates using conservative rules
- add canonical grouped display in admin views and feed generation rules
- show reconciliation metrics in sync status

## Testing Strategy

Tests should cover:

- removed Google events are hidden or marked deleted after sync
- removed iCloud events are hidden or marked deleted after sync
- cancelled events are not treated as active
- repeated sync does not create duplicate local event rows
- duplicate clustering groups exact and near-exact provider events conservatively
- canonical grouped views do not drop provenance
- ICS generation respects canonical visibility rules
- source adapters can ingest normalized appointment candidates without breaking the calendar-provider contract

## Security And Privacy

- keep all ingestion read-only
- continue encrypting provider credentials and secrets at rest
- never log portal credentials, OAuth tokens, app-specific passwords, or message content
- treat non-calendar sources as potentially more sensitive than standard calendar providers
- require explicit operator configuration for any source that is not already a connected calendar account
- document privacy implications before adding reminder or message-derived extraction paths

## Documentation Requirements

Implementation of Phase A or later phases must update:

- `README.md`
- `docs/ops.md`
- `docs/prompts/backend.md`
- relevant GitHub issues and any follow-on issues spawned from the phase decomposition

## Open Questions Resolved For This Spec

- The request is not being treated as permission to add write-back sync.
- The request is not being treated as permission to scrape arbitrary portals without a supported auth path.
- The request is not being treated as permission to ingest iCloud phone backups directly on the server.
- The immediate next slice should be trust and cleanup, not the hardest new connector first.
