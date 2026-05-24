# CalSync Write-Capable Foundation Phase A/B1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor CalSync into a cleaner scheduling-app shell, preserve Apple/iCloud connector data, add calendar role modeling, and lay the writable Google and Microsoft provider foundation without yet shipping full booking pages or public identity expansion.

**Architecture:** Build this slice in three layers. First, introduce schema and service boundaries for provider capabilities and calendar roles. Second, refactor the UI shell and connections experience to reflect those roles while preserving current Apple and Google data. Third, add Microsoft provider scaffolding and writable-provider service interfaces so later slices can implement real create, update, and cancel flows without redesigning the app again.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Jinja templates, PostgreSQL/SQLite test compatibility, pytest

---

## File Structure

### Existing files to modify

- `src/calsync/models/providers.py`
  - extend provider account and calendar records with capability and role metadata
- `src/calsync/models/provider_configurations.py`
  - preserve existing provider settings while making room for Microsoft and writable Google configuration
- `src/calsync/repos/providers.py`
  - read and update writable/provider-role fields
- `src/calsync/repos/provider_config.py`
  - read and update Microsoft provider config alongside Google
- `src/calsync/services/providers/base.py`
  - define read vs write provider capabilities
- `src/calsync/services/providers/google.py`
  - prepare writable scope and capability metadata
- `src/calsync/services/providers/icloud.py`
  - preserve current CalDAV connector data while surfacing capability metadata
- `src/calsync/services/provider_config.py`
  - add Microsoft provider configuration helpers and public capability summaries
- `src/calsync/services/app_settings.py`
  - centralize navigation and shell-level product state where needed
- `src/calsync/web/routes/providers.py`
  - shift from a purely technical provider-settings page toward product-friendly connections context
- `src/calsync/web/routes/accounts.py`
  - evolve the page toward `Connections`
- `src/calsync/web/routes/calendars.py`
  - manage per-calendar role assignment instead of only enable/disable
- `src/calsync/web/routes/dashboard.py`
  - align dashboard framing with the new product shell
- `src/calsync/web/routes/__init__.py`
  - register any new route group
- `src/calsync/web/templates/base.html`
  - new navigation and product shell
- `src/calsync/web/templates/accounts.html`
  - redesign as the new connections entry experience
- `src/calsync/web/templates/providers.html`
  - simplify provider settings and public app URL messaging
- `src/calsync/web/templates/calendars.html`
  - expose availability/booking/reference roles
- `src/calsync/web/templates/dashboard.html`
  - adjust dashboard IA and cleaner product framing
- `src/calsync/web/static/app.css`
  - replace the old muted admin palette with a brighter scheduling-product system
- `README.md`
  - document the new write-capable direction and first-slice scope
- `docs/ops.md`
  - document calendar roles, Microsoft readiness, and Apple preservation expectations
- `docs/prompts/backend.md`
  - capture shipped behavior for issue `#17`

### New files to create

- `alembic/versions/20260524_02_provider_roles_and_capabilities.py`
  - schema migration for account capabilities and per-calendar roles
- `src/calsync/models/scheduling.py`
  - enums or constants for calendar role and provider capability state
- `src/calsync/services/providers/microsoft.py`
  - provider scaffold and discovery contract for Microsoft calendars
- `src/calsync/web/routes/connections.py`
  - clean route layer for product-style connections flow if the existing accounts route becomes too overloaded
- `tests/test_calendar_roles.py`
  - provider-role persistence and UI role-change coverage
- `tests/test_connections_pages.py`
  - connections IA and route behavior
- `tests/test_microsoft_provider.py`
  - provider config and scaffold behavior
- `tests/test_visual_shell.py`
  - top-nav and page shell coverage for the new IA

### Boundaries to preserve

- preserve existing Apple/iCloud account rows and encrypted app-specific passwords
- do not claim real Apple calendar OIDC
- do not implement full booking pages in this slice
- do not implement invited-user login flows in this slice
- do not remove trust, review, problems, or event explain features

---

### Task 1: Add Provider Capability And Calendar Role Schema

**Files:**
- Create: `alembic/versions/20260524_02_provider_roles_and_capabilities.py`
- Create: `src/calsync/models/scheduling.py`
- Modify: `src/calsync/models/providers.py`
- Modify: `src/calsync/models/__init__.py`
- Test: `tests/test_calendar_roles.py`

- [ ] **Step 1: Write the failing schema tests**

```python
def test_provider_account_capabilities_round_trip(migrated_session_factory):
    from calsync.models import ProviderAccount

    with migrated_session_factory() as session:
        account = ProviderAccount(
            provider_type="google",
            account_label="Personal Google",
            remote_account_id="acct-1",
            auth_mode="oauth",
            can_read=True,
            can_write=True,
            requires_reconnect=False,
        )
        session.add(account)
        session.commit()
        account_id = account.id

    with migrated_session_factory() as session:
        reloaded = session.get(ProviderAccount, account_id)
        assert reloaded is not None
        assert reloaded.can_read is True
        assert reloaded.can_write is True
        assert reloaded.auth_mode == "oauth"
```

```python
def test_provider_calendar_role_round_trip(migrated_session_factory):
    from calsync.models import ProviderAccount, ProviderCalendar

    with migrated_session_factory() as session:
        account = ProviderAccount(
            provider_type="icloud",
            account_label="Family iCloud",
            remote_account_id="acct-2",
            auth_mode="caldav",
            can_read=True,
            can_write=False,
        )
        session.add(account)
        session.flush()
        calendar = ProviderCalendar(
            provider_account_id=account.id,
            remote_calendar_id="cal-1",
            display_name="Family",
            timezone="America/Anchorage",
            is_enabled=True,
            calendar_role="availability_only",
        )
        session.add(calendar)
        session.commit()
        calendar_id = calendar.id

    with migrated_session_factory() as session:
        reloaded = session.get(ProviderCalendar, calendar_id)
        assert reloaded is not None
        assert reloaded.calendar_role == "availability_only"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_calendar_roles.py::test_provider_account_capabilities_round_trip tests/test_calendar_roles.py::test_provider_calendar_role_round_trip -v`
Expected: FAIL because capability fields and calendar roles do not exist yet.

- [ ] **Step 3: Add the schema and model fields**

```python
class ProviderAccount(Base):
    __tablename__ = "provider_accounts"

    auth_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="oauth")
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    can_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    requires_reconnect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
```

```python
class ProviderCalendar(Base):
    __tablename__ = "provider_calendars"

    calendar_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="personal_reference",
        server_default="personal_reference",
    )
```

```python
class CalendarRole:
    AVAILABILITY_ONLY = "availability_only"
    CONFLICT_ONLY = "conflict_only"
    WRITABLE_BOOKING_TARGET = "writable_booking_target"
    PERSONAL_REFERENCE = "personal_reference"
    HIDDEN = "hidden"
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_calendar_roles.py tests/test_event_normalization.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alembic src/calsync/models tests/test_calendar_roles.py
git commit -m "feat: add provider capability and calendar role schema"
```

### Task 2: Preserve Existing Apple Data And Surface Capability Metadata

**Files:**
- Modify: `src/calsync/repos/providers.py`
- Modify: `src/calsync/services/providers/icloud.py`
- Modify: `src/calsync/services/providers/google.py`
- Test: `tests/test_calendar_roles.py`

- [ ] **Step 1: Write the failing preservation and capability tests**

```python
def test_existing_icloud_account_defaults_to_read_capable_without_losing_secret(session):
    account = seed_icloud_account(session, encrypted_secret="ciphertext")

    hydrated = get_provider_account(session, account.id)

    assert hydrated.encrypted_credentials == "ciphertext"
    assert hydrated.auth_mode == "caldav"
    assert hydrated.can_read is True
```

```python
def test_google_account_capabilities_reflect_writable_scope_flag(session):
    account = seed_google_account(session, writable_scope_granted=True)

    hydrated = get_provider_account(session, account.id)

    assert hydrated.can_read is True
    assert hydrated.can_write is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_calendar_roles.py -k "icloud_account_defaults or google_account_capabilities" -v`
Expected: FAIL because capability hydration and legacy preservation rules are not applied yet.

- [ ] **Step 3: Implement capability hydration**

```python
def infer_provider_capabilities(account: ProviderAccount) -> tuple[str, bool, bool]:
    if account.provider_type == "icloud":
        return "caldav", True, bool(account.supports_write_back)
    if account.provider_type == "google":
        return "oauth", True, bool(account.oauth_scope_mode == "read_write")
    if account.provider_type == "microsoft":
        return "oauth", True, bool(account.oauth_scope_mode == "read_write")
    return "oauth", True, False
```

```python
def hydrate_provider_account_capabilities(account: ProviderAccount) -> ProviderAccount:
    auth_mode, can_read, can_write = infer_provider_capabilities(account)
    account.auth_mode = auth_mode
    account.can_read = can_read
    account.can_write = can_write
    return account
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_calendar_roles.py tests/test_google_provider.py tests/test_icloud_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/repos/providers.py src/calsync/services/providers/icloud.py src/calsync/services/providers/google.py tests/test_calendar_roles.py
git commit -m "feat: preserve provider capabilities for legacy accounts"
```

### Task 3: Add Microsoft Provider Scaffold And Config Plumbing

**Files:**
- Create: `src/calsync/services/providers/microsoft.py`
- Modify: `src/calsync/services/providers/__init__.py`
- Modify: `src/calsync/services/provider_config.py`
- Modify: `src/calsync/models/provider_configurations.py`
- Modify: `src/calsync/repos/provider_config.py`
- Test: `tests/test_microsoft_provider.py`

- [ ] **Step 1: Write the failing provider config tests**

```python
def test_microsoft_provider_config_round_trip(session):
    save_microsoft_provider_config(
        session,
        client_id="ms-client",
        client_secret="encrypted-secret",
        scopes="openid profile offline_access https://graph.microsoft.com/Calendars.ReadWrite",
    )

    config = load_microsoft_provider_config(session)

    assert config.client_id == "ms-client"
    assert "Calendars.ReadWrite" in config.scopes
```

```python
def test_microsoft_provider_scaffold_reports_oauth_mode():
    provider = MicrosoftCalendarProvider()
    assert provider.provider_type == "microsoft"
    assert provider.auth_mode == "oauth"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_microsoft_provider.py -v`
Expected: FAIL because Microsoft config and provider scaffold do not exist yet.

- [ ] **Step 3: Implement config and provider scaffold**

```python
@dataclass(slots=True)
class MicrosoftProviderConfig:
    client_id: str
    encrypted_client_secret: str | None
    scopes: str
```

```python
class MicrosoftCalendarProvider(CalendarProvider):
    provider_type = "microsoft"
    auth_mode = "oauth"

    def supports_write_back(self) -> bool:
        return True

    def discover_calendars(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
        raise NotImplementedError("Microsoft discovery ships in a later task")
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_microsoft_provider.py tests/test_provider_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/providers/microsoft.py src/calsync/services/providers/__init__.py src/calsync/services/provider_config.py src/calsync/models/provider_configurations.py src/calsync/repos/provider_config.py tests/test_microsoft_provider.py
git commit -m "feat: add microsoft provider scaffold"
```

### Task 4: Refactor The Product Shell And Navigation

**Files:**
- Modify: `src/calsync/web/templates/base.html`
- Modify: `src/calsync/web/templates/dashboard.html`
- Modify: `src/calsync/web/static/app.css`
- Modify: `src/calsync/services/app_settings.py`
- Test: `tests/test_visual_shell.py`
- Test: `tests/test_dashboard_pages.py`

- [ ] **Step 1: Write the failing shell tests**

```python
def test_base_shell_exposes_new_product_navigation(client, seeded_admin_session):
    response = client.get("/admin", follow_redirects=True)

    assert "Connections" in response.text
    assert "Availability" in response.text
    assert "Trust" in response.text
    assert "Settings" in response.text
```

```python
def test_dashboard_uses_scheduling_app_language(client, seeded_admin_session):
    response = client.get("/admin", follow_redirects=True)

    assert "Upcoming schedule" in response.text
    assert "Problems to fix" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visual_shell.py tests/test_dashboard_pages.py -k "product_navigation or scheduling_app_language" -v`
Expected: FAIL because the current shell still reflects the older admin-console IA.

- [ ] **Step 3: Implement the new shell and brighter visual system**

```html
<nav class="shell-nav">
  <a href="/admin">Home</a>
  <a href="/admin/calendar">Calendar</a>
  <a href="/admin/connections">Connections</a>
  <a href="/admin/availability">Availability</a>
  <a href="/admin/problems">Trust</a>
  <a href="/admin/settings">Settings</a>
</nav>
```

```css
:root {
  --bg: #eef6f7;
  --surface: #ffffff;
  --surface-soft: #f7fbfb;
  --ink: #193038;
  --muted: #5f7b83;
  --accent: #0f8b8d;
  --accent-strong: #0a6870;
  --accent-warm: #ffd166;
  --border: #d7e7ea;
  --shadow: 0 16px 40px rgba(20, 70, 83, 0.12);
}
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_visual_shell.py tests/test_dashboard_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/templates/base.html src/calsync/web/templates/dashboard.html src/calsync/web/static/app.css src/calsync/services/app_settings.py tests/test_visual_shell.py tests/test_dashboard_pages.py
git commit -m "feat: refactor scheduling product shell"
```

### Task 5: Replace Accounts With A Real Connections Experience

**Files:**
- Create: `src/calsync/web/routes/connections.py`
- Modify: `src/calsync/web/routes/__init__.py`
- Modify: `src/calsync/web/routes/accounts.py`
- Modify: `src/calsync/web/routes/providers.py`
- Modify: `src/calsync/web/templates/accounts.html`
- Modify: `src/calsync/web/templates/providers.html`
- Test: `tests/test_connections_pages.py`

- [ ] **Step 1: Write the failing connections tests**

```python
def test_connections_page_shows_google_microsoft_and_apple_cards(client, seeded_admin_session):
    response = client.get("/admin/connections", follow_redirects=True)

    assert "Connect a calendar" in response.text
    assert "Google Calendar" in response.text
    assert "Outlook / Microsoft 365" in response.text
    assert "Apple Calendar" in response.text
```

```python
def test_connections_page_keeps_existing_apple_account_visible(client, seeded_admin_session, session):
    seed_icloud_account(session, label="Family iCloud")

    response = client.get("/admin/connections", follow_redirects=True)

    assert "Family iCloud" in response.text
    assert "Apple Calendar" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_connections_pages.py -v`
Expected: FAIL because `/admin/connections` and the new product framing do not exist yet.

- [ ] **Step 3: Implement the connections route and UI**

```python
router = APIRouter(prefix="/admin/connections", tags=["connections"])

@router.get("")
def connections_page(...):
    return templates.TemplateResponse(
        request,
        "accounts.html",
        {
            "google_ready": google_ready,
            "microsoft_ready": microsoft_ready,
            "apple_accounts": apple_accounts,
            "connected_accounts": account_rows,
        },
    )
```

```html
<article class="panel">
  <h2>Connect a calendar</h2>
  <div class="connection-cards">
    <section class="connection-card">
      <h3>Google Calendar</h3>
      <p>Use Google sign-in to connect a writable or availability calendar.</p>
    </section>
    <section class="connection-card">
      <h3>Outlook / Microsoft 365</h3>
      <p>Prepare Microsoft sign-in for writable or availability calendars.</p>
    </section>
    <section class="connection-card">
      <h3>Apple Calendar</h3>
      <p>Keep using your Apple ID email and app-specific password.</p>
    </section>
  </div>
</article>
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_connections_pages.py tests/test_provider_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/routes/connections.py src/calsync/web/routes/__init__.py src/calsync/web/routes/accounts.py src/calsync/web/routes/providers.py src/calsync/web/templates/accounts.html src/calsync/web/templates/providers.html tests/test_connections_pages.py
git commit -m "feat: add cleaner calendar connections experience"
```

### Task 6: Add Calendar Role Assignment UI

**Files:**
- Modify: `src/calsync/web/routes/calendars.py`
- Modify: `src/calsync/repos/providers.py`
- Modify: `src/calsync/web/templates/calendars.html`
- Test: `tests/test_calendar_roles.py`

- [ ] **Step 1: Write the failing role-assignment tests**

```python
def test_calendars_page_renders_role_selector_for_connected_calendar(client, seeded_admin_session, session):
    seed_enabled_calendar(session, role="personal_reference")

    response = client.get("/admin/calendars", follow_redirects=True)

    assert "What this calendar is for" in response.text
    assert "availability_only" in response.text
    assert "writable_booking_target" in response.text
```

```python
def test_calendar_role_update_persists(client, seeded_admin_session, session):
    calendar = seed_enabled_calendar(session, role="personal_reference")

    response = client.post(
        f"/admin/calendars/{calendar.id}/role",
        data={"calendar_role": "availability_only"},
        follow_redirects=True,
    )

    session.refresh(calendar)
    assert response.status_code == 200
    assert calendar.calendar_role == "availability_only"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_calendar_roles.py -k "role_selector or role_update_persists" -v`
Expected: FAIL because role assignment endpoints and UI do not exist yet.

- [ ] **Step 3: Implement role assignment**

```python
@router.post("/{calendar_id}/role")
def update_calendar_role(calendar_id: str, calendar_role: str = Form(...), ...):
    set_calendar_role(session, calendar_id=calendar_id, calendar_role=calendar_role)
    session.commit()
    return RedirectResponse("/admin/calendars", status_code=303)
```

```html
<label>
  What this calendar is for
  <select name="calendar_role">
    <option value="availability_only">Check availability</option>
    <option value="conflict_only">Conflict checking only</option>
    <option value="writable_booking_target">Receive new bookings</option>
    <option value="personal_reference">Personal reference</option>
    <option value="hidden">Hidden</option>
  </select>
</label>
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_calendar_roles.py tests/test_calendars_page.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/routes/calendars.py src/calsync/repos/providers.py src/calsync/web/templates/calendars.html tests/test_calendar_roles.py
git commit -m "feat: add calendar role assignment"
```

### Task 7: Capture Docs, Tracking, And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ops.md`
- Modify: `docs/prompts/backend.md`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Update docs for the first redesign slice**

Document:

- the new `Connections` experience
- Apple connector preservation
- calendar roles such as `availability_only` and `writable_booking_target`
- Microsoft scaffold status
- the new brighter shell and product IA

- [ ] **Step 2: Extend docs coverage**

```python
def test_docs_cover_write_capable_redesign_foundation() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "connections" in readme_content
    assert "writable booking target" in readme_content
    assert "apple connector" in readme_content
    assert "microsoft" in readme_content

    assert "check availability" in ops_content
    assert "receive new bookings" in ops_content
    assert "apple" in ops_content and "app-specific password" in ops_content

    assert "#17" in prompt_content
    assert "write-capable" in prompt_content
    assert "sign in with google" in prompt_content
```

- [ ] **Step 3: Run focused validation**

Run: `pytest tests/test_calendar_roles.py tests/test_microsoft_provider.py tests/test_connections_pages.py tests/test_visual_shell.py tests/test_docs.py -v`
Expected: PASS

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ops.md docs/prompts/backend.md tests/test_docs.py
git commit -m "docs: capture write-capable redesign foundation"
```
