# Backend Prompt Capture

- GitHub issue: `#32`
- Scope: first Apple-first ChatGPT app slice on top of a small CalSync-owned service for conversational calendar write-back

## Interpreted Requirements

- the first conversational scheduling slice should target the shared iCloud family calendar
- ChatGPT should create, edit, and cancel appointments through CalSync instead of talking to Apple directly
- the service should stay small and focused, but it must preserve normalized local appointment records and Apple event mappings
- the shared workspace should act as the operational brain while iCloud remains the family-visible destination
- the initial tool surface should stay narrow and mutation-focused so the experience is reliable before broader search, planning, or reminder automation ships
- the design should leave room for later Google intake, iCloud Reminders sync, structured medical metadata, and Alexa-style voice input

## Behavioral Boundaries

- this slice is Apple/iCloud-first, not a broad multi-provider conversational assistant
- Google inbound event ingestion is future work
- iCloud Reminders sync is future work
- public booking links and broader availability logic are future work
- the first conversational app should expose create, edit, and cancel flows only

## Phase Notes

- issue `#32` builds on the preserved write-capable legacy work from earlier CalSync slices, now archived on `legacy/pre-chatgpt-brain-reset`
- the owned service is the durable contract; ChatGPT should never mutate CalDAV directly
- iCloud remains the family-facing calendar of record for day-to-day visibility
- CalSync should keep audit history and local event mappings so the later family workspace can grow without redesigning this slice
