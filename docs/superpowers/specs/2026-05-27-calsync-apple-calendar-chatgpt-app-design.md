# CalSync Apple-First ChatGPT App Design

## Metadata

- Date: 2026-05-27
- Canonical umbrella issue: `#17`
- Related shipped foundation: `#31`
- Design slice issue: `#32`
- Scope: design the first ChatGPT app slice that creates, edits, and cancels Apple/iCloud calendar appointments through a small CalSync-owned service

## Why This Exists

CalSync already has an operator-facing appointment editor and Apple/iCloud write-back support, but the user's next priority is different: they want to talk to ChatGPT and have it manage the family calendar directly.

The family's real-world workflow is:

- the main shared calendar lives in iCloud
- personal scheduling is effectively shared scheduling
- Google calendars still matter because Gmail naturally produces event context there
- reminders around family and medical appointments are at least as important as the appointment row itself

That means the next product slice should not start with a giant all-in-one family planner. It should start with a safe conversational entry point into the existing Apple-first calendar workflow while keeping the architecture ready for the larger shared-workspace "brain" later.

## Product Promise

The first ChatGPT app slice should let the user say things like:

- "Put Lily's dentist appointment on the family calendar next Tuesday at 2 PM."
- "Move my eye doctor appointment from Thursday to Friday morning."
- "Cancel the follow-up visit and leave a note about why."

and have CalSync carry out that request against the primary iCloud family calendar through a controlled service layer.

## Operator Goals

This slice should satisfy four goals immediately:

1. `Use ChatGPT as a practical calendar entry point`
   - the user should be able to create, edit, and cancel appointments without opening the admin UI first
2. `Keep iCloud as the family-visible destination`
   - family members should continue to see the real calendar in Apple surfaces they already use
3. `Preserve CalSync as the operational brain`
   - CalSync should keep normalized records, event mappings, and audit history
4. `Avoid painting the architecture into a corner`
   - the service contract should be extendable to Google intake, iCloud Reminders sync, medical metadata, and later voice channels such as Alexa

## Recommended Approach

Build:

- a `ChatGPT app` as the conversational front end
- a `small CalSync-owned service` as the only write surface ChatGPT talks to
- an `Apple/iCloud event adapter` behind that service

Do not build:

- direct ChatGPT-to-CalDAV writes
- full Google sync orchestration in this slice
- iCloud Reminders sync yet
- a generalized booking platform
- a giant board or dashboard redesign before the conversational Apple path works

This is the right first slice because it keeps the family-facing behavior simple while putting the durable logic in one owned backend surface.

## System Architecture

### Main components

- `ChatGPT app`
  - exposes the user-facing conversational experience
  - calls CalSync tools instead of touching provider APIs directly
- `CalSync service`
  - validates requests
  - resolves the primary writable iCloud calendar
  - applies create, update, or cancel behavior
  - records normalized appointments and audit history
- `Apple/iCloud calendar connection`
  - remains the real family-facing calendar destination
  - receives the final provider mutation
- `CalSync local data model`
  - stores normalized appointment records
  - stores Apple event mappings
  - stores mutation history for traceability

### High-level flow

1. User asks ChatGPT to create, edit, or cancel an appointment.
2. The ChatGPT app calls the matching CalSync service tool.
3. CalSync validates the payload and resolves the primary writable iCloud calendar.
4. CalSync performs the Apple/iCloud mutation.
5. CalSync writes or updates the normalized local record and event mapping.
6. CalSync returns a structured result for ChatGPT to confirm back to the user.

## Functional Scope

### In scope for v1

- create Apple/iCloud appointments through ChatGPT
- edit Apple/iCloud appointments through ChatGPT
- cancel Apple/iCloud appointments through ChatGPT
- persist local normalized appointment records for each conversational mutation
- persist Apple event mapping references
- keep an audit trail of who changed what and how
- return clear success and failure messages for conversational use

### Out of scope for v1

- Google inbound event ingestion
- iCloud Reminders sync
- public booking links or booking pages
- team routing or Calendly-style lead qualification
- general Monday-style board workflows
- broad availability search
- automatic medical reminder generation

## Data Model Direction

### Core records

- `workspace`
  - one shared family workspace
- `calendar_connection`
  - the configured Apple/iCloud account and writable target calendar
- `appointment`
  - CalSync's normalized appointment record
- `external_event_link`
  - stable mapping between CalSync appointment id and Apple provider event id
- `audit_entry`
  - immutable mutation history

### Appointment fields for this slice

- title
- start time
- end time
- timezone
- all-day flag
- location
- notes
- attendee text block
- status
- source set to `chatgpt_app`

### Reserved extension space

The model should also leave room for structured fields that are not required in v1 but are likely soon:

- patient
- provider name
- facility name
- phone number
- address
- insurance notes
- prep instructions
- follow-up date
- reminder template id

## Sync And Mutation Behavior

### Source-of-truth rule

The shared CalSync workspace is the operational brain, but `iCloud is the main family-facing calendar`.

That means:

- mutations should succeed against Apple/iCloud, not only locally
- the family should continue to see the resulting event in Apple Calendar
- CalSync should preserve the internal mapping and history needed for future automation

### Create behavior

- ChatGPT sends a create request to CalSync
- CalSync validates the appointment payload
- CalSync writes the appointment to the primary writable iCloud calendar
- CalSync stores the resulting provider event reference and normalized appointment record
- ChatGPT receives a structured success response with normalized time values

### Edit behavior

- ChatGPT sends an update request referencing a CalSync appointment id
- CalSync resolves the mapped Apple event
- CalSync updates the provider event first
- CalSync updates the normalized local appointment record second
- ChatGPT receives the updated appointment details and status

### Cancel behavior

- ChatGPT sends a cancel request referencing a CalSync appointment id
- CalSync resolves the mapped Apple event
- CalSync cancels or removes the provider event according to the Apple adapter behavior
- CalSync marks the local appointment canceled and records the audit event
- ChatGPT receives a clear cancellation confirmation

## ChatGPT Tool Surface

The first app should expose only three mutation tools:

- `create_appointment`
- `update_appointment`
- `cancel_appointment`

### Tool payload shape

Each tool should accept a small, human-friendly payload with fields such as:

- title
- date
- start time
- end time
- timezone
- all_day
- location
- notes

The update and cancel flows should also include a stable CalSync appointment id.

### Tool response shape

Each tool should return:

- CalSync appointment id
- mapped Apple event reference
- normalized start and end values
- resulting status
- user-safe confirmation text
- structured error information when the request fails

## Safety And Trust Rules

This slice touches family and medical scheduling, so the service should be conservative.

### Required safeguards

- no write if no primary writable iCloud calendar is configured
- no update or cancel without a stable stored mapping
- no silent recreation when an update target cannot be found
- reject invalid or ambiguous time ranges
- prefer edit-in-place over delete-and-recreate
- record every mutation in audit history
- require confirmation messaging when the user's intent appears destructive or underspecified

### Error handling direction

Conversational failures should be clear and recoverable. Examples:

- missing writable calendar configuration
- appointment id not found
- mapped Apple event missing or stale
- provider write failure
- invalid date, time, or timezone combination

ChatGPT should be able to explain the failure in plain language instead of guessing.

## Why This Is Not Yet The Full Family Brain

The user wants a broader system that eventually includes:

- Google feeding shared events inward
- iCloud Reminders sync for follow-ups
- linked medical reminders and templates
- richer family coordination
- future Alexa voice capture

Those are good goals, but they should build on top of a stable owned service contract rather than being mixed into the first conversational Apple slice.

## Future Expansion Path

After this slice proves reliable, the same service can grow into:

### Shared family workspace logic

- richer appointment records
- family-member associations
- structured medical metadata

### Reminder orchestration

- linked follow-up tasks
- iCloud Reminders sync
- completion syncing back into CalSync

### Intake and automation

- Google event ingestion
- appointment-type templates
- proactive reminder suggestions

### Additional interfaces

- a fuller CalSync control-center UI
- availability and search tools
- Alexa or Echo voice capture flowing into the same backend service

## Non-Goals

- no attempt to replace Apple Calendar as the daily family-facing surface in this slice
- no requirement that ChatGPT become a universal scheduling assistant on day one
- no broad multi-provider search and merge system in the first implementation pass
- no task-board or Monday-style workflow layer before the Apple conversational path is proven

## Success Criteria

This design is successful if the implementation delivers:

- a ChatGPT app that can create, edit, and cancel iCloud appointments through CalSync
- a small owned service boundary instead of direct provider mutation from ChatGPT
- reliable local appointment and mapping persistence
- auditability suitable for family scheduling
- a clean foundation for later Google intake, iCloud Reminders sync, and structured medical workflows

## Recommended Next Step

After spec approval, the next planning pass should turn this into an implementation plan that covers:

- service endpoints and schemas
- local model additions or reuse strategy
- Apple adapter mutation contract reuse
- ChatGPT app tool definitions
- setup and operator configuration flow
- test strategy for create, update, and cancel round trips
