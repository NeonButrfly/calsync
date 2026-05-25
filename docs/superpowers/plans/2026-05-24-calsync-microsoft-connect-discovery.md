# CalSync Microsoft Connect And Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship real Microsoft OAuth account connection, calendar discovery, and event sync so Outlook / Microsoft 365 accounts can participate in the existing CalSync calendar and trust surfaces.

**Architecture:** Reuse the proven Google flow shape. First extend shared settings and provider-config helpers for Microsoft environment fallback and callback generation. Then add Microsoft OAuth routes and provider-service methods for code exchange, account persistence, discovery, refresh, and event fetch. Finally align the Connections UI, docs, and sync pipeline so Microsoft behaves like a first-class read-only provider.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Jinja templates, httpx, Microsoft Graph v1.0, pytest

---

## File Structure

### Existing files to modify

- `src/calsync/config.py`
  - add Microsoft OAuth settings and scope parsing helpers
- `src/calsync/services/provider_config.py`
  - add Microsoft snapshot fallback and runtime config resolution
- `src/calsync/services/providers/microsoft.py`
  - replace scaffold-only adapter with real OAuth/discovery/sync behavior
- `src/calsync/web/routes/accounts.py`
  - update Connections messaging based on actual Microsoft connect readiness
- `src/calsync/web/routes/__init__.py`
  - register the Microsoft route file
- `src/calsync/web/templates/accounts.html`
  - show `Connect Microsoft Account` when appropriate
- `src/calsync/web/templates/providers.html`
  - adjust callback wording now that the callback becomes live
- `src/calsync/services/sync.py`
  - no structural change expected, but validate Microsoft works cleanly through current hooks
- `README.md`
  - document live Microsoft account connection and sync behavior
- `docs/ops.md`
  - document Microsoft setup and operator flow
- `docs/prompts/backend.md`
  - capture issue `#22`

### New files to create

- `src/calsync/web/routes/microsoft.py`
  - Microsoft OAuth start and callback routes
- `tests/test_microsoft_oauth_routes.py`
  - route-level Microsoft OAuth coverage

### Existing tests to extend

- `tests/test_connections_pages.py`
  - Connections page state changes for Microsoft
- `tests/test_microsoft_provider.py`
  - provider-service token, discovery, and fetch behavior
- `tests/test_docs.py`
  - doc coverage for live Microsoft connection and sync

---

### Task 1: Add Microsoft config helpers and failing route tests

**Files:**
- Modify: `src/calsync/config.py`
- Modify: `src/calsync/services/provider_config.py`
- Create: `tests/test_microsoft_oauth_routes.py`

- [ ] **Step 1: Write the failing route tests**

```python
def test_microsoft_start_reports_missing_provider_settings(client: TestClient) -> None:
    response = client.get("/auth/microsoft/start")

    assert response.status_code == 400
    assert "Provider Settings" in response.text
```

```python
def test_microsoft_start_redirects_to_microsoft_when_configured(client: TestClient) -> None:
    response = client.get("/auth/microsoft/start", follow_redirects=False)

    assert response.status_code == 303
    assert "login.microsoftonline.com" in response.headers["location"]
    assert "redirect_uri=" in response.headers["location"]
    assert "state=" in response.headers["location"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_microsoft_oauth_routes.py -q`
Expected: FAIL because Microsoft OAuth routes do not exist yet.

- [ ] **Step 3: Add Microsoft settings helpers**

Implement in `src/calsync/config.py`:

```python
class Settings(BaseSettings):
    microsoft_oauth_client_id: str | None = None
    microsoft_oauth_client_secret: str | None = None
    microsoft_oauth_scopes: str = "openid,offline_access,User.Read,Calendars.Read"
    microsoft_oauth_redirect_path: str = "/auth/microsoft/callback"
```

```python
def build_microsoft_callback_url_from_base(...): ...
def build_microsoft_callback_url(...): ...
def get_microsoft_oauth_scopes(...): ...
```

Extend `src/calsync/services/provider_config.py` so Microsoft runtime config can resolve from database first and environment fallback second, parallel to Google.

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_microsoft_oauth_routes.py tests/test_microsoft_provider.py -q`
Expected: still FAIL on missing routes, but config-level assertions should now be unblocked.

- [ ] **Step 5: Commit**

```bash
git add src/calsync/config.py src/calsync/services/provider_config.py tests/test_microsoft_oauth_routes.py
git commit -m "feat: add Microsoft OAuth config helpers"
```

### Task 2: Add Microsoft OAuth start and callback routes

**Files:**
- Create: `src/calsync/web/routes/microsoft.py`
- Modify: `src/calsync/web/routes/__init__.py`
- Modify: `tests/test_microsoft_oauth_routes.py`

- [ ] **Step 1: Extend the failing callback tests**

```python
def test_microsoft_callback_persists_account_and_redirects_to_calendars(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    start_response = client.get("/auth/microsoft/start", follow_redirects=False)
    state = parse_qs(urlsplit(start_response.headers["location"]).query)["state"][0]

    response = client.get(
        f"/auth/microsoft/callback?state={state}&code=microsoft-code",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/calendars"
```

- [ ] **Step 2: Run callback tests to verify they fail**

Run: `pytest tests/test_microsoft_oauth_routes.py -q`
Expected: FAIL because callback route and persistence do not exist yet.

- [ ] **Step 3: Implement the routes**

Model the route file on the Google flow:

```python
MICROSOFT_OAUTH_SESSION_KEY = "microsoft_oauth_state"

@router.get("/auth/microsoft/start")
def start_microsoft_oauth(...): ...

@router.get("/auth/microsoft/callback")
def microsoft_oauth_callback(...): ...
```

Behavior:

- require authenticated admin session
- generate and persist state in the session
- build Microsoft authorization URL
- on callback, validate state
- handle `error`, missing code, and exchange failures with clean Connections-page messages
- on success, persist account, discover calendars, commit, and redirect to `/admin/calendars`

- [ ] **Step 4: Run route tests**

Run: `pytest tests/test_microsoft_oauth_routes.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/routes/microsoft.py src/calsync/web/routes/__init__.py tests/test_microsoft_oauth_routes.py
git commit -m "feat: add Microsoft OAuth connection routes"
```

### Task 3: Implement Microsoft provider token exchange and account persistence

**Files:**
- Modify: `src/calsync/services/providers/microsoft.py`
- Modify: `tests/test_microsoft_provider.py`

- [ ] **Step 1: Write the failing provider-service tests**

```python
def test_build_microsoft_authorization_url_uses_configured_scopes_and_callback(...): ...
def test_connect_microsoft_account_from_callback_persists_tokens_and_metadata(...): ...
def test_refresh_microsoft_access_token_marks_reconnect_on_invalid_grant(...): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_microsoft_provider.py -q`
Expected: FAIL because the service functions do not exist yet.

- [ ] **Step 3: Implement the provider service layer**

Add:

```python
MICROSOFT_OAUTH_AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_OAUTH_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_ME_URL = "https://graph.microsoft.com/v1.0/me"
MICROSOFT_CALENDARS_URL = "https://graph.microsoft.com/v1.0/me/calendars"
MICROSOFT_EVENTS_URL_TEMPLATE = "https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events"
```

Implement:

- `build_microsoft_authorization_url(...)`
- `connect_microsoft_account_from_callback(...)`
- `exchange_microsoft_code_for_tokens(...)`
- `fetch_microsoft_user_info(...)`
- `persist_microsoft_oauth_account(...)`
- `ensure_microsoft_access_token(...)`
- `refresh_microsoft_access_token(...)`

Keep metadata keys parallel to Google where it helps:

- `microsoft_email`
- `microsoft_subject`
- `microsoft_scopes`
- `microsoft_access_token_expires_at`
- `microsoft_auth_status`
- `microsoft_reconnect_required`
- `microsoft_last_auth_error`

- [ ] **Step 4: Run focused provider tests**

Run: `pytest tests/test_microsoft_provider.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/providers/microsoft.py tests/test_microsoft_provider.py
git commit -m "feat: persist Microsoft OAuth accounts"
```

### Task 4: Implement Microsoft calendar discovery and event sync

**Files:**
- Modify: `src/calsync/services/providers/microsoft.py`
- Modify: `tests/test_microsoft_provider.py`

- [ ] **Step 1: Write the failing discovery and event tests**

```python
def test_microsoft_discovery_maps_calendars(...): ...
def test_microsoft_fetch_events_normalizes_graph_events(...): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_microsoft_provider.py -k "discovery or fetch_events" -q`
Expected: FAIL because adapter methods still raise `NotImplementedError`.

- [ ] **Step 3: Implement discovery and fetch**

Discovery should map Graph calendars to `DiscoveredCalendar` with:

- `external_id`
- `name`
- `timezone`
- `default_enabled=False`
- metadata fields such as `can_write`, `owner`, and `is_default_calendar` when available

Event fetch should normalize Graph events to `NormalizedEvent` with:

- provider identity fields
- title, description, location
- timezone-aware start/end
- all-day support
- cancellation handling when Graph marks events cancelled or removed

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_microsoft_provider.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/providers/microsoft.py tests/test_microsoft_provider.py
git commit -m "feat: add Microsoft calendar discovery and sync"
```

### Task 5: Align Connections and Provider Settings messaging

**Files:**
- Modify: `src/calsync/web/routes/accounts.py`
- Modify: `src/calsync/web/templates/accounts.html`
- Modify: `src/calsync/web/templates/providers.html`
- Modify: `tests/test_connections_pages.py`
- Modify: `tests/test_provider_settings.py`

- [ ] **Step 1: Write the failing messaging tests**

```python
def test_connections_page_shows_connect_microsoft_button_when_configured(...): ...
def test_provider_settings_page_describes_microsoft_callback_as_live_connect_route(...): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_connections_pages.py tests/test_provider_settings.py -q`
Expected: FAIL because the current Microsoft copy still describes scaffold-only account connection.

- [ ] **Step 3: Implement the UI alignment**

Requirements:

- if Microsoft settings are configured, `/admin/accounts` shows `Connect Microsoft Account`
- provider settings should describe the callback as active for the live Microsoft connect flow
- saved-state copy must stay honest about read-only sync versus future write-back

- [ ] **Step 4: Run focused UI tests**

Run: `pytest tests/test_connections_pages.py tests/test_provider_settings.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/routes/accounts.py src/calsync/web/templates/accounts.html src/calsync/web/templates/providers.html tests/test_connections_pages.py tests/test_provider_settings.py
git commit -m "feat: expose live Microsoft connect flow in Connections"
```

### Task 6: Sync docs, prompt capture, and whole-slice verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ops.md`
- Modify: `docs/prompts/backend.md`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Update the docs**

Document:

- live Microsoft account connection
- shared Microsoft app setup and callback expectations
- Microsoft calendar discovery and sync
- Microsoft write-back still deferred to `#23`

- [ ] **Step 2: Add doc coverage**

Add assertions in `tests/test_docs.py` for:

- Microsoft account connection now being real
- Microsoft sync now being real
- Microsoft write-back still future work

- [ ] **Step 3: Run docs tests**

Run: `pytest tests/test_docs.py -q`
Expected: PASS

- [ ] **Step 4: Run full verification**

Run:

```bash
pytest -q
docker compose config
docker compose up --build -d
docker compose ps
```

Expected:

- full test suite passes
- compose config renders cleanly
- stack rebuild succeeds
- `db` healthy, `web` healthy, `worker` running

- [ ] **Step 5: Run live HTTP smoke checks**

Run:

```bash
python - <<'PY'
import urllib.request
for url in [
    "http://127.0.0.1:3080/healthz",
    "http://127.0.0.1:3080/login",
    "http://127.0.0.1:3080/admin/accounts",
]:
    try:
        with urllib.request.urlopen(url) as response:
            print(url, response.status)
    except Exception as exc:
        print(url, exc)
PY
```

Expected:

- `/healthz` returns `200`
- `/login` returns `200`
- unauthenticated `/admin/accounts` redirects or resolves to login

- [ ] **Step 6: Commit**

```bash
git add README.md docs/ops.md docs/prompts/backend.md tests/test_docs.py
git commit -m "docs: capture Microsoft connection and sync slice"
```

