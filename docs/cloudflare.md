# Cloudflare Runtime For CalSync

This decision record is tracked in issue `#36`.

## Live shape

Cloudflare is now part of the real runtime, but only as a thin edge layer.

Live hostnames:

- Pi origin brain: `https://calsync.neonbutterfly.net`
- ChatGPT-first edge Worker: `https://edge-calsync.neonbutterfly.net`

Live Worker:

- script name: `edge-calsync`
- route: `edge-calsync.neonbutterfly.net/*`
- KV namespace binding: `TOKEN_HASHES`

## What Cloudflare owns

- public edge hostname for ChatGPT-facing requests
- Worker auth validation
- feature switches
- request forwarding to the Pi origin
- Cloudflare KV copy of channel token hashes

## What the Pi still owns

- Apple/iCloud credentials
- appointment business logic
- Postgres-backed appointment and audit data
- raw channel token values
- Apple CalDAV write-back

## Why this is the right split

This keeps the scheduling brain on `kayraspi` while giving ChatGPT a stable, narrow, authenticated API surface that is easier to extend later for:

- Shortcuts
- Alexa
- webhook automations

The Worker is not a backend rewrite. It is a public edge proxy.

## Worker project

Worker code lives in:

- `workers/edge-calsync`

Useful commands:

```powershell
npm run cf:whoami
npm run cf:edge:test
npm run cf:edge:deploy
```

## Current auth model

Channels:

- `chatgpt`
- `shortcuts`
- `alexa`
- `webhooks`

Current token source of truth:

- `/home/kay/apps/calsync/.runtime/channel-tokens.json` on `kayraspi`

Current edge validation source:

- Cloudflare KV namespace bound as `TOKEN_HASHES`

## Current deployment note

The Worker and origin are both live, and the edge path has been validated for:

- unauthenticated `401`
- authenticated appointment list
- authenticated create
- authenticated cancel

## Future hardening

The current setup already works, but there is one follow-up improvement worth making:

- give the Pi a dedicated Cloudflare API token in `.env` so `scripts/manage_channel_tokens.py sync-cloudflare` can push hash updates automatically without relying on a workstation-mediated sync step
