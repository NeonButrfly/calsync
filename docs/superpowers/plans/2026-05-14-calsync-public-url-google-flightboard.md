# CalSync Public URL, Google Connect, and Flightboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add admin-managed public app URL settings, use the saved HTTPS hostname to unblock Google account connection from LAN/local browsing contexts, and ship a private admin-only flightboard view for enabled calendars.

**Architecture:** Extend the existing provider-settings flow with one deployment-level `public_base_url` app-state value, then update URL-generation and Google-connect gating to prefer that saved value over the current request host when appropriate. Add a new admin-only flightboard route and template that read from the normalized local event store plus enabled provider calendars, keeping the board private and independent from ICS/public publishing.

**Tech Stack:** FastAPI, Jinja2 templates, SQLAlchemy ORM, `AppState` persistence, pytest, Docker Compose deployment on Raspberry Pi

---

## File Structure

- Modify: `src/calsync/config.py`
  - keep the low-level URL builders here and add explicit support for a saved database-backed public URL override
- Modify: `src/calsync/repos/state.py`
  - add small helper functions for reading and normalizing deployment-level app state used by the web layer
- Create: `src/calsync/services/app_settings.py`
  - centralize public-base-URL resolution, validation, persistence, and precedence so routes do not each reimplement it
- Modify: `src/calsync/web/routes/providers.py`
  - save and render the public app URL in the admin UI alongside Google settings
- Modify: `src/calsync/web/routes/accounts.py`
  - use the resolved public URL when deciding whether Google connect is available and what callback host/operator message to show
- Modify: `src/calsync/web/routes/google.py`
  - ensure callback base selection aligns with the new app-settings service
- Modify: `src/calsync/web/routes/dashboard.py`
  - add the flightboard route or delegate to a new dedicated route module if that stays cleaner
- Create: `src/calsync/web/routes/flightboard.py`
  - private admin-only route for the flightboard page and its enabled-calendar event query
- Modify: `src/calsync/web/templates/base.html`
  - add nav entry for the flightboard page
- Modify: `src/calsync/web/templates/providers.html`
  - render public app URL form fields and clearer Google callback/operator guidance
- Modify: `src/calsync/web/templates/accounts.html`
  - show Google connect whenever the saved public URL is valid and explain the exact callback host in use
- Create: `src/calsync/web/templates/flightboard.html`
  - scrolling board-style UI for enabled-calendar upcoming events
- Modify: `src/calsync/static/app.css`
  - add the board-style layout, scrolling treatment, and high-contrast visuals for the private flightboard
- Modify: `tests/test_provider_settings.py`
  - cover saving and reloading the public app URL plus the provider settings UI messaging
- Modify: `tests/test_google_oauth_routes.py`
  - cover Google connect availability with a saved HTTPS public URL even when browsing from a LAN origin
- Modify: `tests/test_url_generation.py`
  - cover saved app-state public URL precedence over request origin and environment fallback behavior
- Create: `tests/test_flightboard.py`
  - cover authentication, enabled-calendar filtering, event ordering, and rendered board content
- Modify: `README.md`
  - document admin-managed public URL setup, outside access expectations, and Google domain-backed callback setup
- Modify: `docs/ops.md`
  - add operator steps for `https://calsync.neonbutterfly.net` and how to verify Google connect readiness
- Modify: `docs/prompts/backend.md`
  - keep prompt capture aligned with implemented behavior if any wording needs refinement after code lands

### Task 1: Add Public App URL Persistence and Resolution

**Files:**
- Create: `src/calsync/services/app_settings.py`
- Modify: `src/calsync/repos/state.py`
- Modify: `src/calsync/config.py`
- Test: `tests/test_url_generation.py`

- [ ] **Step 1: Write the failing tests for saved public URL precedence**

```python
def test_saved_public_base_url_overrides_request_origin_when_present(tmp_path):
    with _build_client_with_state(
        tmp_path,
        saved_public_base_url="https://calsync.neonbutterfly.net",
        base_url="http://192.168.50.232:3080",
    ) as client:
        response = client.get("/debug/external-url")

    assert response.json() == {
        "url": "https://calsync.neonbutterfly.net/healthz"
    }


def test_google_callback_prefers_saved_https_public_url_over_lan_origin(tmp_path):
    with _build_client_with_state(
        tmp_path,
        saved_public_base_url="https://calsync.neonbutterfly.net",
        base_url="http://192.168.50.232:3080",
    ) as client:
        response = client.get("/debug/google-callback-url")

    assert response.json() == {
        "url": "https://calsync.neonbutterfly.net/auth/google/callback"
    }
```

- [ ] **Step 2: Run the targeted URL-generation tests to verify they fail**

Run: `pytest tests/test_url_generation.py -v`
Expected: FAIL on the new saved-app-state precedence assertions because the app only reads `Settings.public_base_url` today.

- [ ] **Step 3: Add app-settings helpers and wire config builders through them**

```python
PUBLIC_BASE_URL_STATE_KEY = "public_base_url"


def get_saved_public_base_url(session: Session) -> str | None:
    state = get_app_state(session, PUBLIC_BASE_URL_STATE_KEY)
    value = (state.value_text or "").strip() if state is not None else ""
    return value or None


def resolve_public_base_url(
    request: Request,
    *,
    session: Session | None,
    settings: Settings,
) -> str:
    saved_public_url = get_saved_public_base_url(session) if session is not None else None
    if saved_public_url:
        return saved_public_url
    if settings.public_base_url:
        return str(settings.public_base_url)
    return str(request.base_url)
```

```python
def build_external_url(
    request: Request,
    path: str,
    *,
    settings: Settings | None = None,
    public_base_url: str | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    base_url = public_base_url or str(resolved_settings.public_base_url or request.base_url)
    return join_url(base_url, path)
```

- [ ] **Step 4: Run the targeted URL-generation tests to verify they pass**

Run: `pytest tests/test_url_generation.py -v`
Expected: PASS with the new saved-public-URL tests included.

- [ ] **Step 5: Commit the persistence/resolution foundation**

```bash
git add src/calsync/services/app_settings.py src/calsync/repos/state.py src/calsync/config.py tests/test_url_generation.py
git commit -m "feat: add public app url resolution service"
```

### Task 2: Expose Public App URL in Provider Settings

**Files:**
- Modify: `src/calsync/web/routes/providers.py`
- Modify: `src/calsync/web/templates/providers.html`
- Modify: `src/calsync/services/app_settings.py`
- Test: `tests/test_provider_settings.py`

- [ ] **Step 1: Write the failing tests for saving and rendering the public app URL**

```python
def test_provider_settings_can_save_public_base_url(tmp_path):
    with _build_client(tmp_path) as client:
        _login(client, client.app.state.test_totp_secret)

        response = client.post(
            "/admin/providers/public-url",
            data={"public_base_url": "https://calsync.neonbutterfly.net"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/providers?saved=public-url"

        page = client.get("/admin/providers?saved=public-url")
        assert "https://calsync.neonbutterfly.net" in page.text
        assert "Public app URL saved." in page.text
```

- [ ] **Step 2: Run the provider-settings tests to verify they fail**

Run: `pytest tests/test_provider_settings.py -v`
Expected: FAIL because no public-URL save route or UI fields exist yet.

- [ ] **Step 3: Add the public URL form, save route, and success/error rendering**

```python
@router.post("/public-url")
def save_public_base_url_settings(
    request: Request,
    public_base_url: str = Form(""),
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    try:
        save_public_base_url(
            session,
            public_base_url=public_base_url,
        )
    except ValueError as exc:
        return _render_provider_settings_page(
            request,
            session,
            templates,
            current_admin=current_admin,
            error_message=str(exc),
            status_code=400,
        )
    session.commit()
    return RedirectResponse(url="/admin/providers?saved=public-url", status_code=303)
```

```html
<article class="panel">
  <h2>Public App URL</h2>
  <p class="subtle">Use the canonical HTTPS hostname CalSync should publish in external links and OAuth callbacks.</p>
  <form method="post" action="/admin/providers/public-url" class="stack">
    <label>
      Public base URL
      <input type="text" name="public_base_url" value="{{ saved_public_base_url }}" />
    </label>
    <button type="submit">Save Public App URL</button>
  </form>
</article>
```

- [ ] **Step 4: Run the provider-settings tests to verify they pass**

Run: `pytest tests/test_provider_settings.py -v`
Expected: PASS with the new public URL save coverage.

- [ ] **Step 5: Commit the provider-settings UI**

```bash
git add src/calsync/web/routes/providers.py src/calsync/web/templates/providers.html src/calsync/services/app_settings.py tests/test_provider_settings.py
git commit -m "feat: add admin-managed public app url settings"
```

### Task 3: Unblock Google Connect with the Saved HTTPS Hostname

**Files:**
- Modify: `src/calsync/web/routes/accounts.py`
- Modify: `src/calsync/web/routes/google.py`
- Modify: `src/calsync/web/templates/accounts.html`
- Modify: `src/calsync/config.py`
- Modify: `tests/test_google_oauth_routes.py`
- Modify: `tests/test_provider_settings.py`

- [ ] **Step 1: Write the failing tests for Google connect availability from a LAN browser with a saved HTTPS hostname**

```python
def test_accounts_page_allows_google_connect_when_saved_public_url_is_valid(tmp_path):
    with _build_client(
        tmp_path,
        public_base_url=None,
        google_client_id=None,
        google_client_secret=None,
        base_url="http://192.168.50.232:3080",
        seed_provider_settings=True,
        saved_public_base_url="https://calsync.neonbutterfly.net",
    ) as client:
        response = client.get("/admin/accounts")

    assert response.status_code == 200
    assert "Connect Google Account" in response.text
    assert "https://calsync.neonbutterfly.net/auth/google/callback" in response.text
    assert "raw IP addresses" not in response.text
```

```python
def test_google_start_uses_saved_public_url_when_request_origin_is_lan_ip(tmp_path):
    with _build_client(
        tmp_path,
        public_base_url=None,
        google_client_id=None,
        google_client_secret=None,
        base_url="http://192.168.50.232:3080",
        seed_provider_settings=True,
        saved_public_base_url="https://calsync.neonbutterfly.net",
    ) as client:
        response = client.get("/auth/google/start", follow_redirects=False)

    assert response.status_code == 303
    assert "https://accounts.google.com" in response.headers["location"]
    assert "redirect_uri=https%3A%2F%2Fcalsync.neonbutterfly.net%2Fauth%2Fgoogle%2Fcallback" in response.headers["location"]
```

- [ ] **Step 2: Run the Google OAuth route tests to verify they fail**

Run: `pytest tests/test_google_oauth_routes.py tests/test_provider_settings.py -v`
Expected: FAIL because the accounts page still evaluates compatibility primarily from the live request host.

- [ ] **Step 3: Update accounts/google routes to use resolved public URL and clearer operator messaging**

```python
resolved_public_base_url = resolve_public_base_url(
    request,
    session=session,
    settings=request.app.state.settings,
)
callback_url = build_google_callback_url_from_base(
    resolved_public_base_url,
    settings=request.app.state.settings,
)
callback_error = validate_google_callback_url(callback_url)
google_connect_allowed = bool(google_snapshot["configured"]) and callback_error is None
```

```html
{% if google_connect_allowed %}
<p class="subtle">Google sign-in will use <strong>{{ google_callback_url }}</strong>.</p>
<form method="get" action="/auth/google/start">
  <button type="submit">Connect Google Account</button>
</form>
{% endif %}
```

- [ ] **Step 4: Run the Google/provider tests to verify they pass**

Run: `pytest tests/test_google_oauth_routes.py tests/test_provider_settings.py -v`
Expected: PASS with the LAN-browser plus saved-public-URL behavior working.

- [ ] **Step 5: Commit the Google connect unblock**

```bash
git add src/calsync/web/routes/accounts.py src/calsync/web/routes/google.py src/calsync/web/templates/accounts.html src/calsync/config.py tests/test_google_oauth_routes.py tests/test_provider_settings.py
git commit -m "fix: allow google connect through saved public hostname"
```

### Task 4: Add the Private Flightboard Route and Query

**Files:**
- Create: `src/calsync/web/routes/flightboard.py`
- Modify: `src/calsync/main.py`
- Modify: `src/calsync/web/templates/base.html`
- Test: `tests/test_flightboard.py`

- [ ] **Step 1: Write the failing tests for private flightboard authentication and enabled-calendar filtering**

```python
def test_flightboard_requires_authenticated_admin(client: TestClient) -> None:
    response = client.get("/admin/flightboard", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_flightboard_shows_only_enabled_calendar_events(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin/flightboard")

    assert response.status_code == 200
    assert "Morning Standup" in response.text
    assert "Disabled Calendar Event" not in response.text
```

- [ ] **Step 2: Run the flightboard tests to verify they fail**

Run: `pytest tests/test_flightboard.py -v`
Expected: FAIL because the route and template do not exist yet.

- [ ] **Step 3: Add the route, query, and nav link**

```python
router = APIRouter(prefix="/admin/flightboard")


@router.get("")
def flightboard_page(
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    now = datetime.now(UTC)
    window_end = now + timedelta(hours=24)
    events = session.scalars(
        select(Event, ProviderCalendar, ProviderAccount)
        .join(ProviderCalendar, Event.provider_calendar_pk == ProviderCalendar.id)
        .join(ProviderAccount, ProviderCalendar.provider_account_pk == ProviderAccount.id)
        .where(ProviderCalendar.enabled.is_(True))
        .where(Event.ends_at >= now)
        .where(Event.starts_at <= window_end)
        .order_by(Event.starts_at, Event.id)
    ).all()
    return templates.TemplateResponse(
        request,
        "flightboard.html",
        {"current_admin": current_admin, "flight_rows": build_flight_rows(events, now=now)},
    )
```

```html
<a href="/admin/flightboard">Flightboard</a>
```

- [ ] **Step 4: Run the flightboard tests to verify they pass**

Run: `pytest tests/test_flightboard.py -v`
Expected: PASS with the route protected and only enabled-calendar events rendered.

- [ ] **Step 5: Commit the private flightboard route**

```bash
git add src/calsync/web/routes/flightboard.py src/calsync/main.py src/calsync/web/templates/base.html tests/test_flightboard.py
git commit -m "feat: add private calendar flightboard route"
```

### Task 5: Build the Flightboard Template and Styling

**Files:**
- Create: `src/calsync/web/templates/flightboard.html`
- Modify: `src/calsync/static/app.css`
- Modify: `tests/test_flightboard.py`

- [ ] **Step 1: Write the failing rendering assertions for board content and status labels**

```python
def test_flightboard_renders_calendar_name_location_and_status(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin/flightboard")

    assert response.status_code == 200
    assert "Mock Account" in response.text
    assert "Conference Room A" in response.text
    assert "Now" in response.text or "Soon" in response.text
```

- [ ] **Step 2: Run the flightboard tests to verify they fail on missing board rendering**

Run: `pytest tests/test_flightboard.py -v`
Expected: FAIL because the template does not yet render the required display fields and labels.

- [ ] **Step 3: Add the template and scrolling board styles**

```html
{% extends "base.html" %}

{% block title %}CalSync Flightboard{% endblock %}
{% block page_title %}Flightboard{% endblock %}

{% block content %}
<section class="flightboard-shell">
  <header class="flightboard-header">
    <p>Enabled calendars only</p>
    <p>Auto-refresh view for upcoming events</p>
  </header>
  <div class="flightboard-marquee">
    <table class="flightboard-table">
      <thead>
        <tr>
          <th>Time</th>
          <th>Status</th>
          <th>Event</th>
          <th>Calendar</th>
          <th>Location</th>
        </tr>
      </thead>
      <tbody>
        {% for row in flight_rows %}
        <tr>
          <td>{{ row.time_range }}</td>
          <td>{{ row.relative_status }}</td>
          <td>{{ row.title }}</td>
          <td>{{ row.calendar_name }}</td>
          <td>{{ row.location }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
{% endblock %}
```

```css
.flightboard-shell {
  background: linear-gradient(180deg, #0d1b20 0%, #10262e 100%);
  color: #e9f7ef;
  border-radius: 24px;
  padding: 1.5rem;
}

.flightboard-marquee {
  overflow: hidden;
  position: relative;
}

.flightboard-table tbody {
  animation: flightboard-scroll 24s linear infinite;
}
```

- [ ] **Step 4: Run the flightboard tests to verify they pass**

Run: `pytest tests/test_flightboard.py -v`
Expected: PASS with the full board content rendered.

- [ ] **Step 5: Commit the board UI**

```bash
git add src/calsync/web/templates/flightboard.html src/calsync/static/app.css tests/test_flightboard.py
git commit -m "feat: add scrolling private flightboard view"
```

### Task 6: Update Docs and Run Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ops.md`
- Modify: `docs/prompts/backend.md`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write the failing docs assertions for public URL and flightboard coverage**

```python
def test_readme_mentions_public_app_url_and_flightboard() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Public App URL" in readme
    assert "calsync.neonbutterfly.net" in readme
    assert "Flightboard" in readme
```

- [ ] **Step 2: Run the docs tests to verify they fail**

Run: `pytest tests/test_docs.py -v`
Expected: FAIL until the new operator instructions are documented.

- [ ] **Step 3: Update operator docs and prompt capture**

```markdown
## Public App URL

Set the Public App URL in the admin UI to the canonical external HTTPS hostname, for example:

- `https://calsync.neonbutterfly.net`

CalSync uses this value for generated ICS links and Google OAuth callback previews.
```

```markdown
## Flightboard

The private Flightboard page is available to authenticated admins at `/admin/flightboard` and shows upcoming events from enabled calendars only.
```

- [ ] **Step 4: Run the full test suite and deployment checks**

Run: `pytest -v`
Expected: PASS

Run: `docker compose config`
Expected: PASS with no config errors

Run on Pi host after deployment:

```bash
cd ~/apps/calsync
git pull --ff-only origin main
docker compose up --build -d
docker compose ps
curl -sS https://calsync.neonbutterfly.net/healthz
```

Expected:
- web container healthy
- health endpoint returns `{"status":"ok"}`
- Provider Settings shows `https://calsync.neonbutterfly.net`
- Accounts page shows `Connect Google Account`
- Flightboard nav link and page render after admin login

- [ ] **Step 5: Commit docs and final verification updates**

```bash
git add README.md docs/ops.md docs/prompts/backend.md tests/test_docs.py
git commit -m "docs: document public url and flightboard operations"
```

## Self-Review

- Spec coverage:
  - public URL persistence and admin UI: Tasks 1-2
  - Google connect unblock and messaging: Task 3
  - private flightboard route and UI: Tasks 4-5
  - docs and deployment validation: Task 6
- Placeholder scan:
  - no `TODO`, `TBD`, or cross-task “same as above” placeholders remain
- Type consistency:
  - the plan consistently uses `public_base_url`, `resolve_public_base_url`, `/admin/flightboard`, and `flight_rows`

