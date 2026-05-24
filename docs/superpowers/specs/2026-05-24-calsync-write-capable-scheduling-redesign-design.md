# CalSync Write-Capable Scheduling Redesign Design

## Metadata

- Date: 2026-05-24
- Canonical issue: `#17`
- Related issues: `#11`, `#16`, `#3`, `#2`
- Scope: redesign CalSync from a read-only aggregation utility into a write-capable scheduling product with Google, Microsoft, and Apple calendar connections, invited-user foundations, and a cleaner modern interface

## Product Direction

CalSync should evolve from:

- a self-hosted read-only calendar aggregator with trust cleanup

into:

- a self-hosted scheduling product that can connect calendars, explain them, create and modify appointments, and grow into an invited-user public utility later

The target product shape is not a generic clone of Calendly. It is a hybrid:

- `Calendly-style` connection and booking simplicity
- `Fantastical-style` calm usability and saved-view potential
- `CalSync-style` trust, explainability, and self-hosted control

## Goals

- support writable calendar connections where providers allow it
- simplify calendar connection through normal web sign-in for Google and Microsoft
- preserve the current Apple/iCloud CalDAV connector and existing stored app-specific passwords
- refactor the UI so it feels like a polished scheduling app instead of an admin console
- prepare the app for invited users later while keeping the current single-tenant deployment model
- begin planning broader user identity with:
  - email and password plus MFA
  - Sign in with Google
  - Sign in with Microsoft
  - Sign in with Apple

## Non-Goals

- no forced move to multi-tenant SaaS in this redesign
- no breaking migration that loses the current Apple connector or stored credentials
- no fake Apple calendar OAuth flow
- no promise that every provider connection can be as seamless as Google or Microsoft
- no removal of existing trust, review, or problem-to-fix workflows

## Constraints And Provider Reality

### Google

Google can support a normal web OAuth flow on the public CalSync hostname and can support writable calendar scopes.

This redesign should assume:

- public HTTPS hostname is available
- CalSync can register redirect URIs against that hostname
- writable scopes can be requested for create, update, and cancellation flows

### Microsoft / Outlook / Microsoft 365

Microsoft can also support a normal web OAuth flow and writable calendar permissions.

This redesign should introduce:

- Microsoft calendar connection
- Microsoft calendar discovery
- write-capable role modeling similar to Google

### Apple / iCloud

Apple calendar connection should stay on the current CalDAV + app-specific password model.

This is explicit product policy for the redesign:

- keep the current Apple connector path
- preserve already-stored Apple credentials and connected accounts
- improve the user experience around Apple onboarding, but do not pretend it becomes a standard OIDC calendar-connection flow

## Product Architecture

CalSync should remain one integrated product on the public deployment hostname, but the redesign should respect two internal trust zones.

### 1. Identity And Connection Zone

Responsibilities:

- CalSync user authentication
- invited-user management later
- MFA and session security
- Google and Microsoft calendar OAuth connection
- Apple/iCloud CalDAV onboarding
- provider token and credential storage

### 2. Scheduling And Calendar Zone

Responsibilities:

- normalized event graph
- duplicate and trust engine
- availability calculation
- booking page logic
- create, update, reschedule, and cancel flows
- provider write-back orchestration
- reminder and communication hooks later

This split preserves one cohesive user experience while keeping the security and product boundaries legible.

## Identity Model

The redesign needs to distinguish two different identity layers.

### CalSync User Identity

How a human signs into CalSync itself.

Supported or planned:

- email and password plus mandatory MFA
- Sign in with Google
- Sign in with Microsoft
- Sign in with Apple
- invited-user onboarding only

### Provider Calendar Identity

How CalSync gets permission to read or write a connected calendar.

Supported in this redesign:

- Google OAuth with writable calendar scopes
- Microsoft OAuth with writable calendar scopes
- Apple/iCloud CalDAV username plus app-specific password

These must stay separate. A person could log into CalSync using email and password while still connecting Google, Microsoft, and Apple calendars underneath.

## Calendar Role Model

Connected calendars should no longer be treated as only “enabled” or “disabled.”

Each connected calendar should have explicit roles:

- `availability_only`
- `conflict_only`
- `writable_booking_target`
- `personal_reference`
- `hidden`

Each provider account should also expose capability flags:

- readable
- writable
- primary scheduling target
- requires reconnect
- limited by provider mode

This gives CalSync the minimum model needed for Calendly-style booking and safe write-back.

## Scheduling And Write-Back Model

The redesign should support these operations on writable providers:

- create appointment
- reschedule appointment
- cancel appointment
- update title
- update location
- update description
- update attendees where the provider path supports it

Write behavior must be explicit:

- no silent writes to every connected calendar
- every booking flow chooses a destination calendar or default booking target
- availability can read from multiple calendars while write-back targets only one selected calendar unless the user intentionally configures something richer later

## UX Refactor

The current interface should be restructured around a more intuitive product model.

### Primary Navigation

- `Home`
  - today, upcoming, recent changes, top problems
- `Calendar`
  - combined calendar, quick create, filters, command-center views later
- `Availability`
  - working hours, buffers, booking windows
- `Booking Pages`
  - appointment types, durations, routing, confirmation behavior
- `Connections`
  - Google, Microsoft, Apple connections and calendar roles
- `Trust`
  - duplicates, conflicts, stale items, event explainability
- `Settings`
  - profile, MFA, invited users, deployment-level settings

### Connections Experience

The current `Provider Settings` plus `Connected Accounts` split should evolve into a calmer flow:

1. `Connect a calendar`
   - Google
   - Outlook / Microsoft 365
   - Apple Calendar
2. `Choose what this calendar is for`
   - check availability
   - receive new bookings
   - writable scheduling calendar
   - personal reference only
3. `Review connected calendars`
   - sync state
   - write capability
   - role
   - last sync
   - reconnect state

### Visual Direction

The current muted brown and beige control-panel mood should be replaced.

Target look:

- brighter and calmer
- cleaner white or warm-light surfaces
- stronger typography
- clearer spacing and hierarchy
- fresh teal or blue-green accents rather than muddy olive-brown heaviness

The goal is:

- less “depressing admin tool”
- more “trusted planning workspace”

## Public Utility Direction

The redesign should prepare for CalSync to become a broader invited-user utility later.

First boundary:

- single tenant
- invited users only

But the schema and flows should anticipate:

- more than one non-admin user
- per-user booking pages
- provider connections attached to specific users
- role-aware access later

This should be designed forward, but not forced into full SaaS isolation yet.

## Migration Requirements

This redesign must not lose current working Apple/iCloud configuration.

Required migration behavior:

- preserve existing Apple account rows
- preserve encrypted app-specific passwords
- preserve existing discovered calendars and enablement state where compatible
- preserve existing Google connections where possible, even if their scope model later changes
- preserve current trust and reconciliation data unless a new richer model intentionally supersedes it

## Phased Delivery

### Phase A: Product Refactor Foundation

Deliver:

- new information architecture
- brighter UI shell
- `Connections` redesign
- provider role model in schema
- Apple connector preservation
- invited-user groundwork in the auth model and docs

### Phase B: Write-Capable Google And Microsoft

Deliver:

- writable Google scopes and write-back flows
- Microsoft calendar OAuth connection
- Microsoft calendar discovery and sync
- write-target and availability-role settings per calendar

### Phase C: Booking Pages And Availability

Deliver:

- booking pages
- appointment types
- durations
- booking windows and buffers
- write-back booking creation into selected target calendars

### Phase D: Identity Expansion

Deliver:

- Sign in with Google
- Sign in with Microsoft
- Sign in with Apple
- invited-user onboarding
- preserve email and password plus MFA

### Phase E: Trust And Scheduling Intelligence

Deliver:

- richer duplicate and conflict handling in a write-capable world
- source confidence and sticky preference rules integrated with writable sources
- reminders and communication hooks such as Twilio

## Recommended First Implementation Slice

The first real implementation cycle should combine:

- `Phase A`
- the start of `Phase B`

Specifically:

- refactor the interface shell and navigation
- create a clean `Connections` experience
- add provider-role modeling for calendars
- preserve current Apple connector data
- prepare the schema and service boundaries for writable Google and Microsoft providers

This is the safest first slice because it:

- improves how the product feels immediately
- does not risk the current Apple integration
- lays the correct structure before booking and write-back logic expand further

## Success Criteria

This redesign is successful if:

- the product has a credible path from read-only aggregator to write-capable scheduler
- the Apple connector remains intact
- Google and Microsoft can be designed as normal public-web OAuth calendar connections
- the UX stops feeling like a technical admin panel
- the product is structurally ready for invited users and broader public utility later
