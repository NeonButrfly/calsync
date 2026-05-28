# CalSync Cloudflare Edge Worker For ChatGPT Design

- Date: `2026-05-28`
- GitHub issue: `#36`
- Status: `approved design`

## Summary

CalSync should add a dedicated Cloudflare Worker on its own subdomain as a thin authenticated edge proxy in front of the live Apple-first Pi service. The Worker exists to give ChatGPT a stable, secure, ChatGPT-first interface for shared family Apple calendar access without moving the actual scheduling brain or Apple CalDAV write logic off `kayraspi`.

The Worker is not a rewrite of the backend. It is a controlled edge surface that validates channel auth, enforces feature switches, normalizes request and response shapes, and forwards allowed operations to the live origin service at `https://calsync.neonbutterfly.net`.

## Goals

- give ChatGPT a stable edge entrypoint for family Apple calendar access
- keep the scheduling brain and Apple write-back logic on `kayraspi`
- separate public edge concerns from origin scheduling concerns
- support a shared family-assistant model where the user's ChatGPT acts on the shared family calendar
- keep the design open for future channels like Shortcuts, Alexa, and webhook automations

## Non-Goals

- no human-facing web UI
- no migration of Apple CalDAV logic into Cloudflare
- no migration of the origin Postgres-backed backend into Workers
- no multi-user family ChatGPT identity model in v1
- no direct public token administration surface

## Current Reality

The current backend is already live and validated:

- origin hostname: `https://calsync.neonbutterfly.net`
- host: `kayraspi` (`192.168.50.232`)
- service role: Apple-first scheduling brain
- current capabilities: create, update, cancel, and list appointments on the shared iCloud family calendar

Cloudflare account inspection confirmed:

- account id: `8f394c6a3a3905f22b0da1514c947d75`
- zone: `neonbutterfly.net`
- zone id: `118f6d38d05beaac974eb35096df308b`
- zone status: `active`
- at least one existing Worker script already exists in the account

## Recommended Architecture

### Public Edge

A dedicated Worker should be deployed on:

- `edge-calsync.neonbutterfly.net`

This Worker should expose only authenticated machine-facing routes intended for ChatGPT app access first. It should not serve a landing page, dashboard, or public documentation surface.

### Origin Brain

The live Pi-hosted backend at:

- `https://calsync.neonbutterfly.net`

remains the real source of scheduling behavior:

- Apple/iCloud credentials live there
- Apple CalDAV writes happen there
- appointment state and audit data live there
- token source-of-truth lives there

### Responsibility Split

Worker responsibilities:

- validate bearer tokens
- determine channel identity
- enforce feature switches
- validate basic route and payload shape
- attach internal forwarding headers
- normalize caller-facing responses
- forward requests to the origin

Origin responsibilities:

- execute appointment business logic
- talk to Apple/iCloud CalDAV
- persist appointments and audit history
- generate and manage channel tokens
- push token hashes to Cloudflare automatically

## First Worker Surface

The Worker should expose these first routes:

- `POST /v1/appointments`
- `PATCH /v1/appointments/:appointment_id`
- `POST /v1/appointments/:appointment_id/cancel`
- `GET /v1/appointments?date_from=...&date_to=...`

This route set gives ChatGPT enough surface area to:

- create appointments
- update appointments
- cancel appointments
- list appointments in a date window before editing or canceling

The Worker should not expose broader search, routing, or scheduling intelligence in this first slice.

## Authentication Model

### Channel Tokens

The design uses separate bearer tokens per channel, with ChatGPT as the first enabled channel.

Initial channel model:

- `chatgpt`
- `shortcuts`
- `alexa`
- `webhooks`

### Token Lifecycle

The user does not want to manage tokens manually. The system should therefore behave as follows:

- the origin service on `kayraspi` generates channel tokens
- the origin keeps the retrievable source-of-truth token values
- an internal local job on the Pi pushes token hashes into Cloudflare-managed secrets or equivalent Worker-readable secure configuration
- the Worker validates inbound bearer tokens against the Cloudflare-side hashed active token set

There should be no public token administration endpoint in v1.

### Shared Assistant Model

The first ChatGPT experience is shared-ready but single-operator:

- the user's ChatGPT account acts as the family scheduling assistant
- the family calendar is the shared scheduling target
- other family members do not need their own ChatGPT setup in v1

The system should still preserve a clean distinction between:

- `channel identity`
- future `user identity`

so that multi-user expansion remains possible later.

## Feature Switches

The Worker should support channel and capability switches from the start:

- `ENABLE_CHATGPT`
- `ENABLE_SHORTCUTS`
- `ENABLE_ALEXA`
- `ENABLE_WEBHOOKS`
- `ENABLE_ADMIN_ROUTES`

In v1, only `ChatGPT` needs to be enabled, but the Worker contract should be written so later channels can be activated without redesigning the edge layer.

## Request Flow

1. ChatGPT app sends a request to `edge-calsync.neonbutterfly.net`.
2. Worker reads the bearer token.
3. Worker maps the token to a known enabled channel.
4. Worker checks feature switches.
5. Worker validates route and payload shape.
6. Worker forwards the request to `https://calsync.neonbutterfly.net`.
7. Origin backend executes the real appointment logic.
8. Origin returns the result.
9. Worker normalizes the response and returns it to ChatGPT.

## Forwarding Contract

The Worker should forward only explicit fields it understands.

The Worker should add origin-facing headers such as:

- `X-CalSync-Channel`
- `X-CalSync-Request-Id`

This gives the origin a trustworthy channel signal without depending on caller-supplied metadata.

The origin should treat the Worker as the trusted edge and should not require callers to invent internal scheduling metadata.

## Error Handling

The Worker should use clear machine-facing errors:

- `401` for invalid or missing auth
- `403` for disabled channels or disallowed routes
- `400` for request-shape errors
- `502` for origin unavailability or edge-to-origin forwarding failures
- pass through origin business-logic validation errors in a normalized shape

Suggested normalized response envelope:

- `ok`
- `message`
- `data`
- `request_id`

This keeps ChatGPT app behavior stable even if the origin evolves internally.

## Security Boundaries

- no human UI
- no anonymous routes
- no raw token logging
- no Apple credentials in the Worker
- no scheduling state ownership in the Worker
- no origin rewrite into Cloudflare at this stage

The Worker should be treated as a public integration edge, not as the new home of calendar intelligence.

## Testing Strategy

### Local Validation

- unit tests for token validation behavior
- unit tests for feature-switch enforcement
- unit tests for request normalization and origin forwarding
- failure-path tests for invalid auth, disabled channel, and origin-down conditions

### Cloudflare Validation

- verify Worker deployment to the intended account and zone
- verify the dedicated subdomain route on `edge-calsync.neonbutterfly.net`
- verify Worker-to-origin forwarding to `https://calsync.neonbutterfly.net`

### End-To-End Validation

- verify a ChatGPT-first create flow
- verify a ChatGPT-first update flow
- verify a ChatGPT-first cancel flow
- verify a ChatGPT-first list flow
- verify that Apple calendar writes still happen only through the origin

## Relationship To Existing Cloudflare Guidance

The earlier Cloudflare decision record remains correct in one important sense:

- the current Python/Postgres/CalDAV backend should not be rewritten into a Cloudflare Worker as-is

This new design is compatible with that conclusion because it is not a backend rewrite. It is an edge integration layer that sits in front of the existing backend.

That means the repo guidance should distinguish between:

- `full backend migration to Workers`: still not the right move
- `thin edge Worker in front of the existing backend`: now the recommended move for ChatGPT access

## Implementation Shape

The next implementation plan should cover:

1. Worker project structure and Wrangler config
2. environment and secret model
3. auth and feature-switch middleware
4. route handlers for create, update, cancel, and list
5. origin forwarding contract and response normalization
6. origin-side token sync support if needed
7. Cloudflare deployment and route binding
8. end-to-end validation against the live Pi origin
