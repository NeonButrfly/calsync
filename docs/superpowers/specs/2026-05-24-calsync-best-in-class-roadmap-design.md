# CalSync Best-In-Class Roadmap Design

## Metadata

- Date: 2026-05-24
- Canonical umbrella issue: `#11`
- Roadmap slice issue: `#16`
- Scope: rank the next product phases that move CalSync from a trustworthy self-hosted calendar aggregator toward a best-in-class private calendar integration utility

## Why This Exists

CalSync now has a real trust layer:

- provider onboarding for Google and Apple/iCloud
- normalized local event storage
- stale and cancelled event cleanup
- duplicate review and problem-to-fix workflows
- per-event explainability

That foundation matters, but it still leaves a strategic gap: the product does not yet have a ranked roadmap that says what comes next, in what order, and why.

The operator explicitly wants CalSync to become the best calendar integrator possible, not just a solid local aggregator. That means the next work should be chosen against the strongest current product ideas in the market, while still preserving CalSync's private, self-hosted, read-only identity.

## Product Promise

CalSync should aim to become:

> the private, self-hosted system that pulls appointments from everywhere, explains them, keeps them clean, and helps the operator fix scheduling mistakes fast

This is a stronger identity than competing head-on with SaaS planners on every feature. The moat is trust, explainability, and private integration depth.

## Competitive Signals Worth Borrowing

The current market leaders point to a few recurring product strengths:

- `Fantastical`
  - natural-language capture
  - calendar sets
  - duplicate-event combining
  - contextual scheduling helpers
- `Reclaim`
  - smart privacy-aware calendar sync
  - buffers, routines, and time-blocking
  - strong calendar intelligence and analytics
- `Morgen`
  - broad provider integration surface
  - unified calendar-plus-task style model
- `Routine`
  - one place for calendar, tasks, and meeting context
- `Notion Calendar`
  - good availability and booking workflows
  - polished multi-calendar conflict handling
- `Motion`
  - proactive planning and schedule adjustment

The roadmap below intentionally borrows the best ideas from those categories while keeping CalSync grounded in its actual strengths and architecture.

## Design Principle

Every new phase should satisfy three filters before it ships:

1. `Improves trust`
   - the operator should believe the calendar more after the feature than before it
2. `Improves operator speed`
   - common mistakes or confusing cases should become faster to understand and fix
3. `Improves integration reach`
   - the product should become better at pulling useful appointment data from more places without turning into a write-heavy automation tangle

If a feature does not pass at least two of those filters, it should not be the next thing built.

## Ranked Roadmap

### 1. Source Confidence And Sticky Trust Policies

This is the highest-leverage next slice.

Deliver:

- provider-aware source confidence scoring
- sticky trust rules such as:
  - prefer Google over iCloud for this duplicate pair
  - always keep confirmed provider events over reminder-derived copies
  - show both for this specific cluster
- clearer event provenance and “why this copy won” explanations
- visible policy application in the problem inbox and event explain view

Why this is first:

- it makes every current Google and iCloud event smarter immediately
- it compounds the value of the work already shipped in issues `#12` through `#15`
- it prevents later ingestion features from reintroducing confusion

### 2. Connector SDK And Non-Calendar Source Model

Deliver:

- a generalized connector contract for:
  - structured appointment APIs
  - import sources
  - derived reminder sources
- connector registration, sync state, and health status
- a broader source model that can represent more than classic calendars

Why this is second:

- it creates the architecture needed for email-derived reminders, portal integrations, and other future utility features
- it avoids building one-off ingestion paths that do not fit together

### 3. Email And ICS Inbox Appointment Ingestion

Deliver:

- operator-controlled import or forwarding paths for appointment reminders
- parsing of basic reminder-style appointment data into normalized candidate events
- confidence tagging so reminder-derived events do not silently outrank real calendar events

Why this is third:

- it is far more feasible and lower-risk than trying to start with a portal integration or iCloud backup parsing
- it creates a real utility jump for appointments that never reach Google or iCloud cleanly

### 4. Calendar Sets, Saved Views, And Command Center UX

Deliver:

- saved views such as:
  - household
  - medical
  - school
  - travel
- calendar sets and view presets
- a better command-center style dashboard

Why this is fourth:

- it makes the app feel personally useful every day
- it borrows one of the strongest user-facing ideas from Fantastical without needing write-back or planning AI first

### 5. Availability, Booking Links, And Safer Scheduling Surfaces

Deliver:

- availability summaries across enabled sources
- private booking-link style surfaces
- reschedule-safe read-only scheduling helpers

Why this is fifth:

- this is where CalSync starts to become an outward-facing scheduling tool rather than only an inward-facing aggregator
- it is valuable, but it should be built on top of trustworthy canonical events and saved views

### 6. Time Intelligence And Personal Planning Assistance

Deliver:

- focus blocks
- travel and buffer suggestions
- recurring routine suggestions
- “what changed since yesterday?” or “what needs to move?” assistance

Why this is sixth:

- these features are attractive, but they depend on a very trustworthy underlying event graph
- without the earlier roadmap slices, this layer would feel magical but unreliable

## Recommended First Execution Slice

The next actual build should be:

### Source Confidence And Lineage

This slice should extend the existing trust engine rather than starting a totally new subsystem.

Core deliverables:

- source confidence reasons on duplicate groups and event copies
- operator-visible rules for which provider copy should win
- sticky per-cluster and per-provider preference overrides
- event explain upgrades that show confidence and applied policy
- problem inbox actions that feel more decisive and less heuristic

What it intentionally does not do yet:

- no new provider write-back
- no generic booking links yet
- no arbitrary portal scraping
- no iCloud phone backup ingestion

## Data And UX Direction For The First Slice

### Data additions

- preference or policy records for duplicate clusters and source pairings
- confidence reasons attached to preferred copies
- richer event lineage metadata for explanation surfaces

### UX additions

- problem cards that say why Google or iCloud won
- explain pages that show the confidence reason and applied policy
- operator actions to make a preference sticky instead of only one-off
- dashboard or review summaries that show “policy applied” versus “needs attention”

## Non-Goals For This Roadmap Pass

- no attempt to out-build Motion-style full planning automation in one phase
- no attempt to unify tasks, notes, documents, and conferencing in the same immediate slice
- no promise of universal portal login support

## Success Criteria

This roadmap is successful if:

- the repo has one canonical ranked plan instead of scattered “maybe next” ideas
- issue `#16` clearly captures the next product slice
- future work under issue `#11` can be opened as deliberate phases instead of ad hoc feature drift

## External Product References

- [Fantastical on the App Store](https://apps.apple.com/us/app/fantastical-calendar/id718043190)
- [Reclaim feature overview](https://help.reclaim.ai/en/articles/6210740-features-in-reclaim)
- [Morgen documentation](https://docs.morgen.so/)
- [Routine](https://routine.co/)
- [Notion Calendar guide](https://www.notion.com/en-gb/help/guides/getting-started-with-notion-calendar?nxtPslug=getting-started-with-notion-calendar)
- [Motion help center](https://www.usemotion.com/help)
