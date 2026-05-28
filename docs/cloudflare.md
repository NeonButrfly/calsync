# Cloudflare Fit For CalSync

This decision record is tracked in issue `#35`.

## Current Cloudflare Account Snapshot

Cloudflare MCP inspection on `2026-05-28` found:

- zone: `neonbutterfly.net` (`active`)
- Pages projects: `0`
- Workers scripts: `1` existing Worker named `qrandom`
- Cloudflare Tunnels: `0`

## Recommendation

The best Cloudflare fit for the current CalSync codebase is:

- now: Cloudflare Tunnel in front of the existing FastAPI service
- later, if we want Cloudflare-native runtime hosting: Cloudflare Containers after the database is externalized

The current repo is a Python `FastAPI` service with:

- Docker Compose
- a companion Postgres container
- Alembic migrations
- Apple CalDAV write-back

That shape already maps cleanly to a small Linux host such as `kayraspi`. Cloudflare Tunnel can publish the service without opening inbound ports and without forcing an application rewrite.

## Why Tunnel Is The Right First Step

Cloudflare Tunnel is the lowest-risk path because it keeps the current service contract intact:

- keep the API on port `3080`
- keep Docker Compose as the runtime
- keep Postgres and Apple credentials on the origin host
- publish a hostname such as `calsync-api.neonbutterfly.net` through Cloudflare
- optionally protect the hostname with Cloudflare Access later

Cloudflare's current Tunnel docs say Tunnel maps a public hostname to a local service and that remotely-managed tunnels are recommended for most use cases.

## Why Pages Is Not A Fit Right Now

Cloudflare Pages is not a match for the current repo because this project is not a static frontend build. The repo is a stateful backend service with a database and calendar write-back.

## Why Workers Is Not A Fit Right Now

Cloudflare's Python Workers platform can run FastAPI, and Cloudflare's current Python docs say Python Workers support pure Python packages and packages included in Pyodide.

This repo still does not map cleanly to Workers today. That is an inference from the codebase plus the docs because the current service depends on:

- `sqlalchemy`
- `alembic`
- `psycopg[binary]`
- a companion Postgres runtime
- Docker-oriented process and migration flow

Moving this service to Workers would be a real architecture change, not a simple deployment toggle.

## Why Containers Is The Best Cloudflare-Native Future Path

Cloudflare Containers is the closest Cloudflare-native destination because this repo already has a `Dockerfile` and an HTTP service boundary.

Before taking that path, we should first:

1. move Postgres out of the local Compose-only shape
2. point `DATABASE_URL` at a managed Postgres instance
3. decide whether Hyperdrive adds value for connection management
4. keep Apple credentials in Cloudflare-managed secrets instead of host-local `.env`

Until then, Tunnel is the safer production path.

## Wrangler Bootstrap In This Repo

This repo now includes a lightweight local Wrangler bootstrap in `package.json`.

Use:

```powershell
npm install
npm run cf:version
npm run cf:login
npm run cf:whoami
```

Wrangler is useful here for:

- Cloudflare account auth checks
- future Worker, Pages, or Container setup
- future DNS or edge-service management

We are intentionally not committing a `wrangler.jsonc` yet because this repo is not currently a Worker, Pages, or Container deployment target.

## Immediate Publish Path

If we want Cloudflare in front of CalSync without rewriting the app:

1. deploy the current Compose stack to the Linux host
2. install `cloudflared` on that host
3. create a remotely-managed Cloudflare Tunnel
4. map a public hostname to `http://127.0.0.1:3080`
5. verify `/healthz` through the Cloudflare hostname

## Revisit Trigger

Revisit this decision if any of these become true:

- the database moves off the local Compose container
- we want Cloudflare-native runtime hosting instead of `kayraspi`
- we split out a small edge-facing Worker for auth, webhooks, or request shaping
