# CalSync Cloudflare Edge Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a dedicated Cloudflare Worker on `edge-calsync.neonbutterfly.net` that gives ChatGPT authenticated access to the Pi-hosted Apple-first CalSync backend for create, update, cancel, and list appointment flows.

**Architecture:** Keep `https://calsync.neonbutterfly.net` as the real scheduling brain and Apple CalDAV writer. Add a separate TypeScript Worker that validates channel tokens, enforces feature switches, normalizes responses, and forwards approved requests to the origin. Add a small origin-side token utility and a date-range list endpoint so the Worker has a stable, minimal origin contract.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Python token utility scripts, Cloudflare Workers, TypeScript, Wrangler, Vitest, Cloudflare KV

---

## File Structure

### Existing backend files to modify

- `src/calsync/config.py`
  - add Cloudflare/token-sync configuration settings
- `src/calsync/api/routes/appointments.py`
  - add date-range list route and forwarded-channel actor support
- `src/calsync/services/appointments.py`
  - add list-range service method and channel-aware audit actor support
- `src/calsync/schemas/appointments.py`
  - add list-query and list-response models
- `tests/test_appointment_api.py`
  - cover list flow and forwarded actor behavior
- `.gitignore`
  - ignore local runtime token files
- `package.json`
  - add Worker-specific scripts
- `docs/cloudflare.md`
  - update actual deployment steps after implementation
- `docs/ops.md`
  - document token bootstrap and Worker deploy flow
- `README.md`
  - reference Worker location and scripts

### New backend files to create

- `src/calsync/services/channel_tokens.py`
  - generate tokens, hash tokens, persist local token store, sync hashes to Cloudflare KV
- `scripts/manage_channel_tokens.py`
  - local Pi-only token bootstrap/rotate/show/sync CLI
- `tests/test_channel_tokens.py`
  - validate token hashing, local store updates, and KV sync payloads

### New Worker project files to create

- `workers/edge-calsync/package.json`
  - Worker-local dev dependencies and scripts
- `workers/edge-calsync/tsconfig.json`
  - TypeScript config
- `workers/edge-calsync/wrangler.jsonc`
  - Worker name, route, bindings, vars
- `workers/edge-calsync/src/env.ts`
  - environment typings and feature flag parsing
- `workers/edge-calsync/src/auth.ts`
  - bearer-token extraction and KV-backed hash validation
- `workers/edge-calsync/src/origin.ts`
  - origin forwarding helpers
- `workers/edge-calsync/src/responses.ts`
  - normalized response helpers
- `workers/edge-calsync/src/index.ts`
  - Worker entrypoint and route dispatch
- `workers/edge-calsync/test/worker.test.ts`
  - end-to-end Worker-local route/auth/forwarding tests
- `workers/edge-calsync/test/auth.test.ts`
  - token validation tests

## Task 1: Extend The Origin API For The Worker Contract

**Files:**
- Modify: `src/calsync/schemas/appointments.py`
- Modify: `src/calsync/services/appointments.py`
- Modify: `src/calsync/api/routes/appointments.py`
- Test: `tests/test_appointment_api.py`

- [ ] **Step 1: Write failing tests for date-range list and forwarded actor behavior**

```python
def test_list_appointments_returns_matching_date_window(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    client.post(
        "/api/appointments",
        json={
            "title": "Dentist",
            "date": "2026-06-01",
            "start_time": "10:00",
            "end_time": "11:00",
            "timezone": "America/Anchorage",
        },
    )
    response = client.get(
        "/api/appointments?date_from=2026-06-01&date_to=2026-06-02"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["title"] == "Dentist"


def test_create_appointment_uses_forwarded_channel_as_actor(monkeypatch) -> None:
    _configure_test_env(monkeypatch)
    monkeypatch.setattr(
        AppointmentService,
        "_build_apple_client",
        lambda self: FakeAppleClient(),
    )
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/appointments",
        headers={"X-CalSync-Channel": "chatgpt"},
        json={
            "title": "Therapy",
            "date": "2026-06-03",
            "start_time": "09:00",
            "end_time": "10:00",
            "timezone": "America/Anchorage",
        },
    )

    assert response.status_code == 201
```

- [ ] **Step 2: Run the targeted backend tests and verify the current failures**

Run:

```powershell
pytest tests/test_appointment_api.py -v
```

Expected:

- list test fails because `GET /api/appointments` does not exist yet
- forwarded actor test only proves create still works and does not yet assert actor behavior in storage

- [ ] **Step 3: Add list schemas for the Worker-facing date-range contract**

```python
class AppointmentListItem(BaseModel):
    appointment_id: str
    title: str
    status: str
    date: str
    start_time: str
    end_time: str
    timezone: str
    all_day: bool
    location: str | None = None
    notes: str | None = None
    attendees_text: str | None = None
    provider_event_id: str | None = None


class ListAppointmentsResponse(BaseModel):
    items: list[AppointmentListItem]
```

- [ ] **Step 4: Add `list_range` and channel-aware actor support in `AppointmentService`**

```python
def create(
    self,
    payload: CreateAppointmentRequest,
    *,
    actor: str = "api",
) -> AppointmentResponse:
    ...
    session.add(
        AuditEntry(
            appointment_id=appointment.id,
            action="create_appointment",
            actor=actor,
            payload_json=payload.model_dump(),
        )
    )


def list_range(
    self,
    *,
    date_from: str,
    date_to: str,
) -> ListAppointmentsResponse:
    start = datetime.fromisoformat(f"{date_from}T00:00:00")
    end = datetime.fromisoformat(f"{date_to}T23:59:59")
    with self.session_factory() as session:
        rows = session.execute(
            select(Appointment, AppointmentExternalLink)
            .join(
                AppointmentExternalLink,
                AppointmentExternalLink.appointment_id == Appointment.id,
                isouter=True,
            )
            .where(Appointment.starts_at >= start)
            .where(Appointment.starts_at <= end)
            .order_by(Appointment.starts_at.asc())
        ).all()
        ...
```

- [ ] **Step 5: Add `GET /api/appointments` and forward `X-CalSync-Channel` into the service actor**

```python
@router.get("", response_model=ListAppointmentsResponse)
def list_appointments(
    date_from: str,
    date_to: str,
) -> ListAppointmentsResponse:
    try:
        return AppointmentService().list_range(date_from=date_from, date_to=date_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: CreateAppointmentRequest,
    x_calsync_channel: str | None = Header(default=None),
) -> AppointmentResponse:
    actor = f"worker:{x_calsync_channel}" if x_calsync_channel else "api"
    return AppointmentService().create(payload, actor=actor)
```

- [ ] **Step 6: Finish the actor assertion in the backend test**

```python
from sqlalchemy import select

from calsync.db import _get_engine_for_url
from calsync.models import AuditEntry

...
    session_factory = _get_session_factory_for_url(get_settings().database_url)
    with session_factory() as session:
        audit_entry = session.scalar(select(AuditEntry).order_by(AuditEntry.created_at.desc()))
    assert audit_entry is not None
    assert audit_entry.actor == "worker:chatgpt"
```

- [ ] **Step 7: Run the targeted backend tests and the full backend test suite**

Run:

```powershell
pytest tests/test_appointment_api.py -v
pytest -v
```

Expected:

- the new list test passes
- the forwarded-actor test passes
- full suite passes with no regressions

- [ ] **Step 8: Commit the origin contract changes**

```bash
git add src/calsync/schemas/appointments.py src/calsync/services/appointments.py src/calsync/api/routes/appointments.py tests/test_appointment_api.py
git commit -m "feat: add worker-facing appointment list contract"
```

## Task 2: Add Pi-Local Channel Token Management And Cloudflare KV Sync

**Files:**
- Modify: `.gitignore`
- Modify: `src/calsync/config.py`
- Create: `src/calsync/services/channel_tokens.py`
- Create: `scripts/manage_channel_tokens.py`
- Test: `tests/test_channel_tokens.py`

- [ ] **Step 1: Write failing tests for token hashing and KV sync payload generation**

```python
from calsync.services.channel_tokens import (
    ChannelTokenManager,
    hash_token,
)


def test_hash_token_is_stable_sha256_hex() -> None:
    digest = hash_token("secret-token")
    assert len(digest) == 64
    assert digest == hash_token("secret-token")


def test_manager_builds_cloudflare_kv_payload(tmp_path) -> None:
    manager = ChannelTokenManager(runtime_path=tmp_path / "channel-tokens.json")
    token = manager.bootstrap_channel("chatgpt")
    payload = manager.build_cloudflare_kv_payload()

    assert payload["chatgpt"]["hash"] == hash_token(token)
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run:

```powershell
pytest tests/test_channel_tokens.py -v
```

Expected:

- import error because `channel_tokens.py` does not exist yet

- [ ] **Step 3: Add Cloudflare token-sync configuration to `src/calsync/config.py`**

```python
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_token_kv_namespace_id: str | None = None
    channel_token_runtime_path: str = ".runtime/channel-tokens.json"
```

- [ ] **Step 4: Implement `ChannelTokenManager` and hash helpers**

```python
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ChannelTokenManager:
    def __init__(self, *, runtime_path: Path) -> None:
        self.runtime_path = runtime_path

    def bootstrap_channel(self, channel: str) -> str:
        token = secrets.token_urlsafe(32)
        data = self._load()
        data[channel] = {"token": token, "hash": hash_token(token)}
        self._save(data)
        return token

    def build_cloudflare_kv_payload(self) -> dict[str, dict[str, str]]:
        data = self._load()
        return {
            channel: {"hash": value["hash"]}
            for channel, value in data.items()
        }
```

- [ ] **Step 5: Implement a Pi-local CLI in `scripts/manage_channel_tokens.py`**

```python
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="command", required=True)

bootstrap = subparsers.add_parser("bootstrap")
bootstrap.add_argument("--channels", required=True)

rotate = subparsers.add_parser("rotate")
rotate.add_argument("--channel", required=True)

show = subparsers.add_parser("show")
show.add_argument("--channel", required=True)

sync = subparsers.add_parser("sync-cloudflare")
```

- [ ] **Step 6: Add Cloudflare KV sync support to `ChannelTokenManager`**

```python
def sync_hashes_to_cloudflare(
    self,
    *,
    account_id: str,
    api_token: str,
    namespace_id: str,
) -> None:
    payload = self.build_cloudflare_kv_payload()
    headers = {"Authorization": f"Bearer {api_token}"}
    for channel, value in payload.items():
        httpx.put(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{channel}",
            headers=headers,
            content=value["hash"],
            timeout=30,
        ).raise_for_status()
```

- [ ] **Step 7: Ignore the local runtime token file**

```gitignore
.runtime/
```

- [ ] **Step 8: Run token tests**

Run:

```powershell
pytest tests/test_channel_tokens.py -v
```

Expected:

- token hashing passes
- payload generation passes

- [ ] **Step 9: Commit the token-management slice**

```bash
git add .gitignore src/calsync/config.py src/calsync/services/channel_tokens.py scripts/manage_channel_tokens.py tests/test_channel_tokens.py
git commit -m "feat: add Cloudflare channel token sync utilities"
```

## Task 3: Scaffold The Dedicated Worker Project

**Files:**
- Modify: `package.json`
- Create: `workers/edge-calsync/package.json`
- Create: `workers/edge-calsync/tsconfig.json`
- Create: `workers/edge-calsync/wrangler.jsonc`
- Create: `workers/edge-calsync/src/env.ts`
- Create: `workers/edge-calsync/src/index.ts`
- Test: `workers/edge-calsync/test/worker.test.ts`

- [ ] **Step 1: Write a failing Worker smoke test**

```ts
import { env, createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import worker from "../src/index";

describe("edge worker smoke", () => {
  it("returns 401 when auth is missing", async () => {
    const request = new Request("https://edge-calsync.neonbutterfly.net/v1/appointments");
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);
    await waitOnExecutionContext(ctx);
    expect(response.status).toBe(401);
  });
});
```

- [ ] **Step 2: Run the Worker smoke test and confirm the expected failure**

Run:

```powershell
npm --prefix workers/edge-calsync test
```

Expected:

- package or file-not-found failure because the Worker project does not exist yet

- [ ] **Step 3: Create the Worker-local package and TypeScript config**

```json
{
  "name": "edge-calsync-worker",
  "private": true,
  "type": "module",
  "scripts": {
    "deploy": "wrangler deploy",
    "dev": "wrangler dev",
    "test": "vitest run"
  },
  "devDependencies": {
    "@cloudflare/vitest-pool-workers": "^0.8.0",
    "@cloudflare/workers-types": "^4.20260524.0",
    "typescript": "^5.8.0",
    "vitest": "^3.2.0",
    "wrangler": "^4.95.0"
  }
}
```

- [ ] **Step 4: Create `wrangler.jsonc` with the dedicated subdomain route**

```jsonc
{
  "name": "edge-calsync",
  "main": "src/index.ts",
  "compatibility_date": "2026-05-28",
  "workers_dev": false,
  "routes": [
    {
      "pattern": "edge-calsync.neonbutterfly.net/*",
      "zone_name": "neonbutterfly.net"
    }
  ],
  "kv_namespaces": [
    {
      "binding": "TOKEN_HASHES",
      "id": "REPLACE_WITH_REAL_NAMESPACE_ID"
    }
  ],
  "vars": {
    "ORIGIN_BASE_URL": "https://calsync.neonbutterfly.net",
    "ENABLE_CHATGPT": "true",
    "ENABLE_SHORTCUTS": "false",
    "ENABLE_ALEXA": "false",
    "ENABLE_WEBHOOKS": "false",
    "ENABLE_ADMIN_ROUTES": "false"
  }
}
```

- [ ] **Step 5: Add root convenience scripts**

```json
"scripts": {
  "cf:login": "wrangler login",
  "cf:version": "wrangler --version",
  "cf:whoami": "wrangler whoami",
  "cf:edge:dev": "npm --prefix workers/edge-calsync run dev",
  "cf:edge:test": "npm --prefix workers/edge-calsync run test",
  "cf:edge:deploy": "npm --prefix workers/edge-calsync run deploy"
}
```

- [ ] **Step 6: Add the minimal Worker environment types and `fetch` export**

```ts
export interface WorkerEnv {
  TOKEN_HASHES: KVNamespace;
  ORIGIN_BASE_URL: string;
  ENABLE_CHATGPT: string;
  ENABLE_SHORTCUTS: string;
  ENABLE_ALEXA: string;
  ENABLE_WEBHOOKS: string;
  ENABLE_ADMIN_ROUTES: string;
}

export default {
  async fetch(): Promise<Response> {
    return new Response("not implemented", { status: 501 });
  },
};
```

- [ ] **Step 7: Run the Worker smoke test again**

Run:

```powershell
npm --prefix workers/edge-calsync install
npm --prefix workers/edge-calsync test
```

Expected:

- the test now runs and fails on `501 != 401`

- [ ] **Step 8: Commit the Worker scaffold**

```bash
git add package.json package-lock.json workers/edge-calsync/package.json workers/edge-calsync/tsconfig.json workers/edge-calsync/wrangler.jsonc workers/edge-calsync/src/env.ts workers/edge-calsync/src/index.ts workers/edge-calsync/test/worker.test.ts
git commit -m "feat: scaffold Cloudflare edge worker project"
```

## Task 4: Implement Worker Auth, Feature Switches, And Origin Forwarding

**Files:**
- Create: `workers/edge-calsync/src/auth.ts`
- Create: `workers/edge-calsync/src/origin.ts`
- Create: `workers/edge-calsync/src/responses.ts`
- Modify: `workers/edge-calsync/src/index.ts`
- Test: `workers/edge-calsync/test/auth.test.ts`
- Test: `workers/edge-calsync/test/worker.test.ts`

- [ ] **Step 1: Write failing auth and forwarding tests**

```ts
it("rejects invalid bearer tokens", async () => {
  const request = new Request("https://edge-calsync.neonbutterfly.net/v1/appointments", {
    headers: { Authorization: "Bearer wrong-token" },
  });
  const response = await worker.fetch(request, env, createExecutionContext());
  expect(response.status).toBe(401);
});

it("forwards list requests for valid chatgpt tokens", async () => {
  await env.TOKEN_HASHES.put("chatgpt", await sha256Hex("real-token"));
  const request = new Request(
    "https://edge-calsync.neonbutterfly.net/v1/appointments?date_from=2026-06-01&date_to=2026-06-02",
    { headers: { Authorization: "Bearer real-token" } },
  );
  const response = await worker.fetch(request, env, createExecutionContext());
  expect(response.status).toBe(200);
});
```

- [ ] **Step 2: Run the Worker tests and verify the current failures**

Run:

```powershell
npm --prefix workers/edge-calsync test
```

Expected:

- invalid token test fails because auth is not implemented
- forwarding test fails because route handling is not implemented

- [ ] **Step 3: Implement token extraction and KV-backed hash validation**

```ts
export async function validateChannelToken(
  request: Request,
  env: WorkerEnv,
): Promise<string | null> {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) {
    return null;
  }
  const token = header.slice("Bearer ".length);
  const hash = await sha256Hex(token);
  for (const channel of ["chatgpt", "shortcuts", "alexa", "webhooks"]) {
    const expected = await env.TOKEN_HASHES.get(channel);
    if (expected && expected === hash) {
      return channel;
    }
  }
  return null;
}
```

- [ ] **Step 4: Implement feature-switch parsing and normalized response helpers**

```ts
export function isEnabled(value: string | undefined): boolean {
  return value === "true";
}

export function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
```

- [ ] **Step 5: Implement origin forwarding with internal headers**

```ts
export async function forwardToOrigin(
  env: WorkerEnv,
  request: Request,
  path: string,
  init: RequestInit,
  channel: string,
  requestId: string,
): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("X-CalSync-Channel", channel);
  headers.set("X-CalSync-Request-Id", requestId);
  return fetch(new URL(path, env.ORIGIN_BASE_URL), {
    ...init,
    headers,
  });
}
```

- [ ] **Step 6: Implement the four first Worker routes**

```ts
if (url.pathname === "/v1/appointments" && request.method === "GET") {
  return forwardListAppointments(...);
}
if (url.pathname === "/v1/appointments" && request.method === "POST") {
  return forwardCreateAppointment(...);
}
if (url.pathname.match(/^\\/v1\\/appointments\\/[^/]+$/) && request.method === "PATCH") {
  return forwardUpdateAppointment(...);
}
if (url.pathname.match(/^\\/v1\\/appointments\\/[^/]+\\/cancel$/) && request.method === "POST") {
  return forwardCancelAppointment(...);
}
```

- [ ] **Step 7: Return `401`, `403`, `400`, and `502` in normalized JSON**

```ts
return jsonResponse(401, {
  ok: false,
  message: "Authentication required.",
  data: null,
  request_id: requestId,
});
```

- [ ] **Step 8: Re-run the Worker test suite**

Run:

```powershell
npm --prefix workers/edge-calsync test
```

Expected:

- auth tests pass
- forwarding tests pass with mocked origin behavior

- [ ] **Step 9: Commit the Worker behavior slice**

```bash
git add workers/edge-calsync/src/auth.ts workers/edge-calsync/src/origin.ts workers/edge-calsync/src/responses.ts workers/edge-calsync/src/index.ts workers/edge-calsync/test/auth.test.ts workers/edge-calsync/test/worker.test.ts
git commit -m "feat: implement Cloudflare edge worker forwarding"
```

## Task 5: Deploy The Worker And Validate Against The Live Pi Origin

**Files:**
- Modify: `workers/edge-calsync/wrangler.jsonc`
- Modify: `docs/cloudflare.md`
- Modify: `docs/ops.md`
- Modify: `README.md`

- [ ] **Step 1: Create the Cloudflare KV namespace for token hashes**

Run:

```powershell
npx wrangler kv namespace create TOKEN_HASHES
```

Expected:

- Wrangler prints a namespace id
- copy that id into `workers/edge-calsync/wrangler.jsonc`

- [ ] **Step 2: Bootstrap the chatgpt channel token on the Pi**

Run on `kayraspi`:

```bash
cd /home/kay/apps/calsync
python scripts/manage_channel_tokens.py bootstrap --channels chatgpt,shortcuts,alexa,webhooks
python scripts/manage_channel_tokens.py sync-cloudflare
```

Expected:

- local runtime token file created under `.runtime/channel-tokens.json`
- Cloudflare KV contains hashes for the configured channels

- [ ] **Step 3: Deploy the Worker**

Run:

```powershell
npm run cf:edge:deploy
```

Expected:

- Wrangler deploys `edge-calsync`
- route attaches to `edge-calsync.neonbutterfly.net/*`

- [ ] **Step 4: Verify unauthenticated edge behavior**

Run:

```powershell
curl -i https://edge-calsync.neonbutterfly.net/v1/appointments?date_from=2026-06-01^&date_to=2026-06-02
```

Expected:

- `401 Unauthorized`
- normalized JSON response

- [ ] **Step 5: Verify authenticated list behavior using the Pi-stored chatgpt token**

Run on `kayraspi`:

```bash
CHATGPT_TOKEN=$(python scripts/manage_channel_tokens.py show --channel chatgpt)
curl -s -H "Authorization: Bearer ${CHATGPT_TOKEN}" "https://edge-calsync.neonbutterfly.net/v1/appointments?date_from=2026-06-01&date_to=2026-06-30"
```

Expected:

- `200 OK`
- appointment JSON payload from the live origin

- [ ] **Step 6: Verify authenticated create and cancel against the live Apple family calendar**

Run on `kayraspi`:

```bash
CHATGPT_TOKEN=$(python scripts/manage_channel_tokens.py show --channel chatgpt)
CREATE_RESPONSE=$(curl -s -X POST "https://edge-calsync.neonbutterfly.net/v1/appointments" \
  -H "Authorization: Bearer ${CHATGPT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Edge Worker verification","date":"2026-06-20","start_time":"10:00","end_time":"10:30","timezone":"America/Anchorage"}')
APPOINTMENT_ID=$(python -c "import json,sys; print(json.load(sys.stdin)['data']['appointment_id'])" <<< "${CREATE_RESPONSE}")
curl -s -X POST "https://edge-calsync.neonbutterfly.net/v1/appointments/${APPOINTMENT_ID}/cancel" \
  -H "Authorization: Bearer ${CHATGPT_TOKEN}"
```

Expected:

- create returns `ok: true`
- cancel returns `ok: true`
- Apple write-back continues to succeed via the origin service

- [ ] **Step 7: Update docs to reflect the real deployed Worker path**

```markdown
- Worker project lives in `workers/edge-calsync`
- `edge-calsync.neonbutterfly.net` is the ChatGPT-first edge hostname
- `calsync.neonbutterfly.net` remains the Pi-hosted origin brain
- token hashes live in Cloudflare KV, token source-of-truth lives on the Pi
```

- [ ] **Step 8: Run final validation**

Run:

```powershell
pytest -v
npm --prefix workers/edge-calsync test
docker compose config
```

Expected:

- backend tests pass
- Worker tests pass
- origin compose config still renders

- [ ] **Step 9: Commit the deployment and docs updates**

```bash
git add workers/edge-calsync/wrangler.jsonc docs/cloudflare.md docs/ops.md README.md
git commit -m "feat: deploy Cloudflare edge worker for ChatGPT access"
```

## Self-Review

### Spec coverage

- dedicated Worker subdomain: covered in Tasks 3 and 5
- ChatGPT-first route surface: covered in Tasks 1 and 4
- Pi remains the scheduling brain: preserved throughout all tasks
- automatic token handling from the Pi: covered in Task 2 and Task 5
- no human-facing UI: preserved because no UI task exists

### Placeholder scan

- no `TBD`
- no unresolved route names
- no undefined file paths

### Type consistency

- Worker routes consistently use `/v1/appointments`
- origin routes consistently use `/api/appointments`
- token store consistently uses channel-name keys
- list contract consistently uses `date_from` and `date_to`
