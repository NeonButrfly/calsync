# CalSync Cloudflare MCP Server Design

- Date: `2026-05-28`
- GitHub issue: `#37`
- Status: `approved design`

## Summary

CalSync should add a dedicated authenticated remote MCP server on Cloudflare so ChatGPT and future MCP-capable clients can access the live Apple-first scheduling system through MCP tools instead of the raw HTTP edge API. The MCP layer should stay thin and tool-focused: it translates MCP tool calls into requests against the already-deployed `edge-calsync` Worker, while `kayraspi` remains the real scheduling brain.

This slice should be built as a separate Cloudflare Worker on its own subdomain. It should be fully write-capable from day one even if some ChatGPT plans only expose read or fetch MCP behavior in practice. The backend and edge API should still support full create, update, cancel, and list behavior so the same system can later power Alexa or other clients without redesign.

## Goals

- expose CalSync as a real remote MCP server
- keep the shared Apple calendar logic on `kayraspi`
- avoid duplicating appointment business logic across MCP, edge, and origin layers
- require authentication from day one
- support the full appointment tool set: list, create, update, cancel
- keep the design open for future Alexa layering

## Non-Goals

- no human-facing web UI
- no rewrite of the Pi backend into Workers
- no rewrite of the existing `edge-calsync` Worker into an MCP server
- no migration of Apple credentials off the Pi
- no family-member-specific ChatGPT identities in v1
- no separate Alexa-specific scheduling brain

## Current Reality

The current deployed stack already exists and is validated:

- origin scheduling brain: `https://calsync.neonbutterfly.net`
- authenticated HTTP edge Worker: `https://edge-calsync.neonbutterfly.net`
- current edge route set:
  - `GET /v1/appointments`
  - `POST /v1/appointments`
  - `PATCH /v1/appointments/{appointment_id}`
  - `POST /v1/appointments/{appointment_id}/cancel`
- current backend route set:
  - `GET /api/appointments`
  - `POST /api/appointments`
  - `PATCH /api/appointments/{appointment_id}`
  - `POST /api/appointments/{appointment_id}/cancel`
- current family calendar write-back is live through Apple CalDAV on the Pi

What is missing is the MCP protocol layer:

- there is no `/mcp` endpoint
- there are no MCP tool descriptors
- there is no MCP auth flow
- ChatGPT cannot treat the deployment as a custom remote MCP app yet

## Recommended Architecture

### Layering

The system should become a three-layer stack:

1. `kayraspi origin`
   - source of scheduling truth
   - Apple credentials and CalDAV writes
   - appointment persistence and audit history
2. `edge-calsync Worker`
   - channel-aware authenticated HTTP API
   - forwards to origin
   - remains useful for non-MCP clients
3. `mcp-calsync Worker`
   - authenticated remote MCP server
   - tool-only client-facing protocol adapter
   - translates MCP tool calls into calls to `edge-calsync`

### Why A Separate MCP Worker

This should not be merged into the existing edge Worker.

Keeping the MCP server separate:

- isolates ChatGPT and MCP protocol concerns from the lower-level HTTP edge API
- avoids coupling tool metadata and OAuth behavior to every future API client
- keeps the raw channel API stable for Alexa, Shortcuts, and other automations
- makes it easier to test MCP behavior independently from edge forwarding behavior

## MCP Server Shape

### Archetype

This should be a `tool-only` remote MCP server.

There is no need for a widget UI in the first slice because the user wants functional calendar access through ChatGPT, not a human-facing browser surface. If a UI becomes useful later, it can be added as a separate follow-on slice without changing the core tool contract.

### Transport

The MCP server should expose a remote MCP endpoint at:

- `https://mcp-calsync.neonbutterfly.net/mcp`

It should use the standard remote MCP HTTP transport expected by ChatGPT and MCP tooling.

### Runtime Model

The first MCP Worker should stay stateless.

There is no current need for Durable Objects because:

- appointment state already lives in the origin database
- tool calls are independent request-response operations
- the MCP layer is an adapter, not the scheduling brain

If future MCP-specific session state or richer elicitation flows become necessary, that can be a later enhancement rather than part of v1.

## Tool Surface

The MCP server should expose four tools:

- `list_appointments`
- `create_appointment`
- `update_appointment`
- `cancel_appointment`

### list_appointments

Purpose:

- give ChatGPT or another MCP client a safe way to inspect a date window before mutating anything

Required inputs:

- `date_from`
- `date_to`

Behavior:

- calls `GET /v1/appointments`
- returns compact normalized appointment data for the requested range

### create_appointment

Purpose:

- create a new Apple/iCloud-backed appointment through the existing backend

Expected inputs:

- title
- start time
- end time
- timezone
- all-day flag
- location
- notes

Behavior:

- calls `POST /v1/appointments`
- returns local appointment id, provider event id, normalized appointment fields, and status

### update_appointment

Purpose:

- edit an existing appointment by known id

Expected inputs:

- `appointment_id`
- one or more mutable appointment fields

Behavior:

- calls `PATCH /v1/appointments/{appointment_id}`
- preserves the origin as the only place where business rules are enforced
- should encourage `list_appointments` first when the caller does not already know the id

### cancel_appointment

Purpose:

- cancel an existing appointment by known id

Expected inputs:

- `appointment_id`

Behavior:

- calls `POST /v1/appointments/{appointment_id}/cancel`
- returns a confirmation payload with the affected appointment and provider ids

## Tool Guidance

The MCP server should return concise server instructions during initialization.

Recommended instruction shape:

- use `list_appointments` before `update_appointment` or `cancel_appointment` unless the caller already has a known appointment id
- treat appointment ids as authoritative
- do not infer destructive edits when the appointment match is ambiguous

This keeps the model’s behavior safer without pushing scheduling logic into the MCP layer.

## Authentication Model

### Client-To-MCP Auth

The MCP server should require authentication from day one.

Recommended approach:

- use OAuth-protected remote MCP access rather than a public authless server
- use Cloudflare Access as the first auth provider so access can be limited to the intended operator account without inventing a separate user-management system

Why this is the right first auth model:

- no manual token juggling for everyday use
- strong gate around family calendar data
- compatible with the authenticated remote MCP model described by Cloudflare
- keeps future expansion possible if a different identity provider is needed later

### MCP-To-Edge Auth

The MCP Worker should not expose the existing edge channel token to MCP clients.

Instead:

- the MCP Worker stores a dedicated internal edge credential as a Worker secret
- every tool call from the MCP Worker to `edge-calsync` includes that secret
- the edge layer continues to validate the request as the `chatgpt` channel

This preserves the existing channel model while keeping the lower-level edge token hidden behind the MCP boundary.

### Identity Model

V1 remains shared-ready but single-operator:

- the user’s ChatGPT account acts as the family scheduling assistant
- the target calendar remains shared
- the system should still log a distinction between MCP caller identity and the lower-level internal channel identity where practical

## Deployment Shape

The MCP Worker should be deployed separately from the current edge Worker on:

- `mcp-calsync.neonbutterfly.net`

The current edge Worker should stay on:

- `edge-calsync.neonbutterfly.net`

The origin should stay on:

- `calsync.neonbutterfly.net`

This gives each layer one clear role and avoids turning a single Worker into a mixed MCP plus raw API surface.

## Request Flow

1. An MCP client connects to `https://mcp-calsync.neonbutterfly.net/mcp`.
2. The MCP server authenticates the client through the configured auth flow.
3. The client invokes one of the appointment tools.
4. The MCP Worker validates the tool input shape.
5. The MCP Worker forwards the tool call to `https://edge-calsync.neonbutterfly.net`.
6. The edge Worker validates the internal credential and routes to origin.
7. The Pi backend executes the real Apple-backed appointment logic.
8. The result flows back through edge to the MCP Worker.
9. The MCP Worker normalizes the result into an MCP tool response.

## Error Handling

The MCP layer should be thin but clear about failures:

- auth failure: block connection or tool use with an authentication error
- bad tool input: return a validation error before forwarding when possible
- edge unreachable: return a normalized upstream failure
- origin validation failure: preserve the user-meaningful error message in the tool response
- ambiguous write intent: prefer a safe failure and nudge the caller to list first

The MCP server should not leak raw backend secrets, raw token material, or implementation-specific internal diagnostics.

## Testing Strategy

### MCP Unit Tests

- tool registration tests
- input-schema validation tests
- edge client tests for list, create, update, and cancel mappings
- auth enforcement tests
- normalized error response tests

### Local Runtime Validation

- run the MCP server locally
- validate `/mcp` connectivity with MCP Inspector
- verify authenticated tool discovery
- verify successful list and write operations against a controlled backend target where appropriate

### Live Validation

- deploy the Worker to the Cloudflare account already used by CalSync
- verify the `mcp-calsync.neonbutterfly.net` route
- verify the MCP Worker can call the live edge Worker
- verify list, create, update, and cancel behavior through the full stack when auth allows it

## Documentation And Tracking

This slice should produce:

- this design spec
- a written implementation plan
- MCP-specific setup and ops documentation
- ChatGPT connection notes that clearly distinguish product-plan limitations from backend capability
- issue `#37` evidence with deployment and validation results

## Product Caveat

The MCP server should still be fully write-capable even though ChatGPT plan support may limit which MCP actions are actually available in some contexts.

That distinction matters:

- CalSync infrastructure should support full writes
- ChatGPT product permissions may still limit write execution for some plan types

This is not a reason to build a read-only MCP server. It is a reason to keep the server fully capable while treating plan-level ChatGPT behavior as an external product constraint.

## Future Alexa Path

Alexa should layer onto the same scheduling system, not a parallel one.

The MCP server is useful even if Alexa later uses a different interface because the architecture stays consistent:

- origin stays the scheduling brain
- edge stays the authenticated machine API
- MCP becomes one of several client-facing adapters

If Alexa later needs a voice-optimized adapter, that adapter should still reuse the same lower-level appointment actions rather than branching calendar logic into a separate stack.

## Implementation Shape

The implementation plan should cover:

1. MCP Worker project layout and dependency choice
2. auth model and Cloudflare configuration
3. tool schemas and tool registration
4. internal edge client and secret model
5. tests for auth, tool mapping, and failure behavior
6. local Inspector validation
7. Cloudflare deployment and route binding
8. live end-to-end validation
