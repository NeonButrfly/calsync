# CalSync Problem Inbox Actions And Event Explain View Design

Date: 2026-05-23  
GitHub issue: `#15`  
Status: Approved design for implementation planning

## Goal

Make CalSync easier to trust and easier to operate by:

- adding more direct actions to the `Problem to fix` inbox
- adding a per-event explain page that answers why an appointment is visible, hidden, preferred, grouped, or in trouble

This slice builds on the trust-review work from issues `#12`, `#13`, and `#14`.

## Problem

CalSync can now identify duplicates, sync failures, and reconnect problems, but the operator still has to jump between pages to understand or resolve common appointment mistakes. The current inbox tells the operator what is wrong, but not enough about the event itself, and not enough about which copy should be kept.

The app needs a clearer operator loop:

1. see the problem
2. understand the event
3. choose the fix
4. return to a clean inbox

## Recommended Approach

Use an `action-first inbox` backed by a single `event explain page`.

Why this approach:

- it makes the inbox immediately more useful instead of turning it into a navigation directory
- it gives CalSync one canonical deep-dive surface for event trust state
- it keeps duplicate handling conservative and read-only while still feeling much smarter

Alternatives considered:

1. Explain page first, then inbox actions later  
This is cleaner in isolation but delays the user-visible value of the inbox.

2. Full trust workbench now  
This would bundle ignore rules, advanced conflict scoring, and more action types at once. It is too large for the next slice and risks slowing down the operator experience instead of sharpening it.

## Scope

### In scope

- richer duplicate actions inside `/admin/problems`
- a new private explain page for one event
- provider-aware duplicate actions such as keeping the Google or iCloud copy when present
- direct links from problem cards into the explain page
- reuse of current read-only trust and sync state

### Out of scope

- destructive source deletion
- provider write-back
- global ignore-rule management
- advanced fuzzy conflict resolution beyond the current conservative grouping model
- email- or portal-based new ingestion sources

## Operator Experience

### Problem inbox

Route:

- `/admin/problems`

For duplicate problems, the inbox should support:

- `Keep preferred copy`
- `Keep Google copy` when a Google copy exists
- `Keep iCloud copy` when an iCloud copy exists
- `Show both`
- `Explain this event`

For sync or auth problems, the inbox should keep direct actions such as:

- `Sync now`
- `Open sync status`
- `Open accounts`
- `Reconnect in accounts`

The operator should be able to fix straightforward duplicate issues from the inbox without detouring into review unless deeper comparison is needed.

### Event explain page

Route shape:

- `/admin/events/{event_id}`

This page should explain one appointment in plain operator language.

It should show:

- title
- start and end time
- location
- provider account and calendar
- event visibility state
- canonical group membership when present
- all known grouped copies of the same appointment
- which copy is preferred
- why that copy is preferred in practical terms
- last sync context from the owning account
- any current sync or auth trouble related to that source

It should also provide direct actions where safe:

- `Keep this copy`
- `Show both copies`
- `Open accounts`
- `Open sync status`

## Service Design

### Problem model extension

Extend the current problem service so duplicate problems carry enough structured data to power better actions:

- canonical group id
- preferred event id
- grouped event ids
- provider types present in the group

This avoids parsing labels in templates and keeps operator actions deterministic.

### Event explanation view model

Add a small service-layer view model that assembles event trust state from:

- `Event`
- `EventGroup`
- grouped event copies
- provider account metadata
- latest account sync log

The explain service should return a single shaped object that templates can render without embedding reconciliation rules in HTML.

### Action handling

Duplicate actions should reuse the existing reconciliation operations where possible:

- prefer event in group
- restore hidden duplicate

The new action layer should mostly adapt operator intent into those existing primitives rather than adding new trust state types.

## UI Design

### Problem inbox cards

Duplicate problem cards should become a bit richer:

- include a stronger action cluster
- surface provider-specific keep actions only when relevant
- always include an `Explain this event` deep link

The inbox should still stay compact and scannable. It should not try to become a full comparison table.

### Event explain page layout

Recommended sections:

1. event summary
2. trust state
3. grouped source copies
4. sync/source status
5. available actions

This keeps the page understandable even when there are multiple copies and one source has auth trouble.

## Behavioral Rules

- Duplicate handling remains conservative and read-only.
- CalSync may hide extra copies from active views, but it must not delete raw provider events.
- Provider-specific keep actions are only shown when that provider has a copy in the group.
- `Show both` only affects local visibility state.
- The explain page must not expose secrets, tokens, raw auth data, or encrypted credential values.

## Testing

Add or update tests for:

- problem inbox rendering of provider-aware duplicate actions
- problem inbox rendering of `Explain this event`
- event explain page requires authenticated admin
- event explain page shows grouped source copies and visibility state
- event explain page shows preferred copy and source context
- duplicate actions from the explain page update local visibility/preference correctly
- full regression coverage for existing dashboard and review flows

Validation gates:

- `pytest -v`
- `docker compose config`
- Pi redeploy and live health checks

## Documentation Updates

Update:

- `README.md`
- `docs/ops.md`
- `docs/prompts/backend.md`

Docs should reflect:

- the new `/admin/events/{event_id}` explain flow
- the richer `/admin/problems` action model
- the operator mental model of “see problem, inspect event, choose fix”

## Risks

- The inbox could become noisy if too many actions appear at once. Keep the action set tight and provider-aware.
- The explain page could expose low-value internals if it mirrors raw tables too literally. Prefer operator language over schema language.
- Preference logic should stay consistent with existing reconciliation behavior; the explain page must describe current rules accurately rather than inventing new ones.

## Success Criteria

- The operator can resolve common duplicate issues directly from `/admin/problems`.
- Any suspicious appointment can be explained from one page without database spelunking.
- The dashboard, inbox, review page, and explain page all describe the same trust state consistently.
- The live Pi deployment remains healthy after rollout.
