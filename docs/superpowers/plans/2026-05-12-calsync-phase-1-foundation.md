# CalSync Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade Phase 1 vertical slice of CalSync with FastAPI, PostgreSQL, first-run admin setup, mandatory MFA, mock provider aggregation, combined calendar UI, tokenized ICS publishing, Docker Compose deployment, and operator documentation.

**Architecture:** CalSync is a modular FastAPI monolith with server-rendered templates and shared domain services, deployed as separate `web` and `worker` containers against one PostgreSQL database. The UI, sync status, and ICS feeds read normalized local state only; provider behavior enters through adapter interfaces so Phase 2 Google and Phase 3 iCloud/CalDAV can plug in without rewriting auth, storage, or publishing.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, Alembic, PostgreSQL, psycopg, Pydantic Settings, passlib/argon2, pyotp, qrcode, cryptography/Fernet, icalendar, pytest, httpx, uvicorn, typer, docker compose, uv

---

## File Structure

### Runtime and packaging

- `pyproject.toml`: Python project metadata, runtime dependencies, test dependencies, and tool config.
- `uv.lock`: locked Python dependencies.
- `.env.example`: documented default configuration including `APP_HOST=0.0.0.0` and `APP_PORT=3080`.
- `.gitignore`: Python, env, test, and local runtime ignores.
- `Dockerfile`: shared image for web and worker roles.
- `docker-compose.yml`: `web`, `worker`, and `db` services with configurable host port publishing.

### Application package

- `src/calsync/__init__.py`: package marker.
- `src/calsync/config.py`: typed settings, URL generation helpers, and logging-safe config access.
- `src/calsync/logging.py`: structured logging filters that redact sensitive fields.
- `src/calsync/db.py`: engine/session setup and dependency helpers.
- `src/calsync/crypto.py`: Fernet-based encryption and decryption helpers.
- `src/calsync/models/*.py`: SQLAlchemy models split by concern.
- `src/calsync/schemas/*.py`: Pydantic form/response models.
- `src/calsync/repos/*.py`: persistence helpers for users, app state, accounts, calendars, events, feeds, and sync logs.
- `src/calsync/services/auth.py`: password hashing, session, MFA, and recovery code logic.
- `src/calsync/services/bootstrap.py`: first-run setup gating and emergency reset helpers.
- `src/calsync/services/providers/base.py`: provider adapter protocol.
- `src/calsync/services/providers/mock.py`: deterministic sample provider implementation.
- `src/calsync/services/events.py`: normalization and dedupe upserts.
- `src/calsync/services/publishing.py`: ICS feed generation and token rotation.
- `src/calsync/services/sync.py`: manual/mock sync orchestration and sync log recording.
- `src/calsync/web/deps.py`: auth/session dependencies for routes.
- `src/calsync/web/routes/*.py`: setup, auth, dashboard, calendars, feeds, sync, and health routes.
- `src/calsync/web/templates/*.html`: server-rendered UI templates.
- `src/calsync/web/static/app.css`: base styles.
- `src/calsync/main.py`: FastAPI app factory and startup logging.
- `src/calsync/worker.py`: worker loop entrypoint.
- `src/calsync/cli.py`: operator commands such as admin password and MFA reset.

### Database and seed assets

- `alembic.ini`: Alembic configuration.
- `alembic/env.py`: migration environment.
- `alembic/versions/*.py`: initial schema migration.

### Tests

- `tests/conftest.py`: test app, test database/session, and fixture wiring.
- `tests/test_health_smoke.py`: basic app-factory and health-route coverage.
- `tests/test_setup_flow.py`: first-run setup and lockout behavior.
- `tests/test_password_policy.py`: strong password validation.
- `tests/test_mfa.py`: TOTP secret generation, otpauth URI formatting, QR generation, and verification behavior.
- `tests/test_recovery_codes.py`: one-time recovery code behavior.
- `tests/test_auth_login.py`: password + MFA login flow.
- `tests/test_mock_provider.py`: calendar discovery and sync with mock data.
- `tests/test_event_normalization.py`: normalized event storage and dedupe behavior.
- `tests/test_ics_publishing.py`: ICS generation and token rotation.
- `tests/test_url_generation.py`: request host vs `PUBLIC_BASE_URL` behavior.
- `tests/test_cli_resets.py`: break-glass local reset commands preserve configuration.
- `tests/test_dashboard_pages.py`: protected admin page behavior.
- `tests/test_worker_config.py`: worker/default config and deployment docs checks.
- `tests/test_docs.py`: README required-content audit.

### Documentation

- `README.md`: overview, setup, Docker, MFA, emergency resets, LAN notes, backups, and limitations.
- `docs/ops.md`: operator workflows, backup/restore commands, and emergency procedures.
- `docs/prompts/backend.md`: capture the behavior-changing prompt and resulting interpreted requirements.

## Task 1: Scaffold The Project And Tooling

**Files:**
- Create: `C:\code\calsync\pyproject.toml`
- Create: `C:\code\calsync\.gitignore`
- Create: `C:\code\calsync\.env.example`
- Create: `C:\code\calsync\src\calsync\__init__.py`
- Create: `C:\code\calsync\src\calsync\main.py`
- Create: `C:\code\calsync\tests\conftest.py`
- Test: `C:\code\calsync\tests\test_health_smoke.py`

- [ ] **Step 1: Write the failing smoke test for the app factory**

```python
from fastapi.testclient import TestClient

from calsync.main import create_app


def test_health_endpoint_is_registered():
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `pytest tests/test_health_smoke.py -v`
Expected: FAIL because `calsync.main` or `create_app` does not exist yet.

- [ ] **Step 3: Create the project skeleton and minimal app factory**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="CalSync")

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: Add project metadata and dependencies**

```toml
[project]
name = "calsync"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "jinja2>=3.1.4",
  "sqlalchemy>=2.0.36",
  "psycopg[binary]>=3.2.3",
  "alembic>=1.14.0",
  "pydantic-settings>=2.6.1",
  "passlib[argon2]>=1.7.4",
  "pyotp>=2.9.0",
  "qrcode[pil]>=7.4.2",
  "cryptography>=43.0.3",
  "icalendar>=5.0.12",
  "python-multipart>=0.0.17",
  "typer>=0.12.5",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-asyncio>=0.24.0",
  "httpx>=0.27.2",
  "beautifulsoup4>=4.12.3",
]
```

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `pytest tests/test_health_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit the scaffolding**

```bash
git add pyproject.toml .gitignore .env.example src/calsync/__init__.py src/calsync/main.py tests/test_health_smoke.py
git commit -m "chore: scaffold calsync application package"
```

## Task 2: Add Typed Settings, Startup Logging, And Database Wiring

**Files:**
- Create: `C:\code\calsync\src\calsync\config.py`
- Create: `C:\code\calsync\src\calsync\logging.py`
- Create: `C:\code\calsync\src\calsync\db.py`
- Modify: `C:\code\calsync\src\calsync\main.py`
- Test: `C:\code\calsync\tests\test_url_generation.py`

- [ ] **Step 1: Write the failing settings and URL-generation tests**

```python
from calsync.config import Settings


def test_default_bind_settings():
    settings = Settings.model_validate({})

    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 3080


def test_public_base_url_overrides_request_origin():
    settings = Settings.model_validate({"public_base_url": "https://calendar.example"})

    assert settings.build_external_url("/feeds/combined") == "https://calendar.example/feeds/combined"
```

- [ ] **Step 2: Run the settings tests to verify they fail**

Run: `pytest tests/test_url_generation.py -v`
Expected: FAIL because `Settings` and URL helpers do not exist.

- [ ] **Step 3: Implement typed settings and safe URL generation**

```python
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", case_sensitive=False)

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=3080, alias="APP_PORT")
    public_base_url: AnyHttpUrl | None = Field(default=None, alias="PUBLIC_BASE_URL")

    def build_external_url(self, path: str) -> str:
        base = str(self.public_base_url).rstrip("/") if self.public_base_url else f"http://localhost:{self.app_port}"
        return f"{base}{path}"
```

- [ ] **Step 4: Add startup logging and database session wiring**

```python
logger.info("Starting CalSync", extra={
    "bind_host": settings.app_host,
    "bind_port": settings.app_port,
    "public_base_url": str(settings.public_base_url) if settings.public_base_url else None,
    "healthcheck_url": settings.build_external_url("/healthz"),
})
```

- [ ] **Step 5: Run the URL-generation tests**

Run: `pytest tests/test_url_generation.py -v`
Expected: PASS

- [ ] **Step 6: Commit the config foundation**

```bash
git add src/calsync/config.py src/calsync/logging.py src/calsync/db.py src/calsync/main.py tests/test_url_generation.py
git commit -m "feat: add application settings and startup logging"
```

## Task 3: Create The Initial Schema And Persistence Layer

**Files:**
- Create: `C:\code\calsync\alembic.ini`
- Create: `C:\code\calsync\alembic\env.py`
- Create: `C:\code\calsync\alembic\versions\20260512_01_initial_schema.py`
- Create: `C:\code\calsync\src\calsync\models\admin.py`
- Create: `C:\code\calsync\src\calsync\models\app_state.py`
- Create: `C:\code\calsync\src\calsync\models\providers.py`
- Create: `C:\code\calsync\src\calsync\models\events.py`
- Create: `C:\code\calsync\src\calsync\models\publishing.py`
- Create: `C:\code\calsync\src\calsync\repos\users.py`
- Create: `C:\code\calsync\src\calsync\repos\state.py`
- Create: `C:\code\calsync\src\calsync\repos\events.py`
- Test: `C:\code\calsync\tests\test_event_normalization.py`

- [ ] **Step 1: Write the failing duplicate-prevention test**

```python
def test_upsert_event_reuses_existing_provider_identity(session, normalized_event):
    first = upsert_event(session, normalized_event)
    second = upsert_event(session, normalized_event)

    assert first.id == second.id
    assert session.query(Event).count() == 1
```

- [ ] **Step 2: Run the event test to verify it fails**

Run: `pytest tests/test_event_normalization.py::test_upsert_event_reuses_existing_provider_identity -v`
Expected: FAIL because models and `upsert_event` do not exist.

- [ ] **Step 3: Implement the schema with provider-identity uniqueness**

```python
__table_args__ = (
    UniqueConstraint(
        "provider_type",
        "provider_account_id",
        "provider_calendar_id",
        "provider_event_id",
        name="uq_events_provider_identity",
    ),
)
```

- [ ] **Step 4: Add Alembic migration for admin, provider, event, feed, and sync tables**

```python
op.create_table(
    "published_feeds",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("scope_type", sa.String(length=32), nullable=False),
    sa.Column("token", sa.String(length=128), nullable=False, unique=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
)
```

- [ ] **Step 5: Run the event test**

Run: `pytest tests/test_event_normalization.py -v`
Expected: PASS for duplicate prevention and normalized-event persistence.

- [ ] **Step 6: Commit the persistence layer**

```bash
git add alembic.ini alembic src/calsync/models src/calsync/repos tests/test_event_normalization.py
git commit -m "feat: add initial database schema and repositories"
```

## Task 4: Implement Password Policy, MFA Services, And Recovery Codes

**Files:**
- Create: `C:\code\calsync\src\calsync\crypto.py`
- Create: `C:\code\calsync\src\calsync\services\auth.py`
- Create: `C:\code\calsync\src\calsync\schemas\auth.py`
- Test: `C:\code\calsync\tests\test_password_policy.py`
- Test: `C:\code\calsync\tests\test_mfa.py`
- Test: `C:\code\calsync\tests\test_recovery_codes.py`

- [ ] **Step 1: Write the failing password and MFA tests**

```python
def test_password_policy_rejects_short_password():
    errors = validate_password_strength("short1!")
    assert any("at least 12 characters" in error for error in errors)


def test_totp_secret_and_uri_generation():
    enrollment = build_totp_enrollment("admin@example.com")

    assert enrollment.secret
    assert enrollment.otpauth_uri.startswith("otpauth://totp/")


def test_recovery_code_can_only_be_used_once():
    codes = generate_recovery_codes()
    stored = store_recovery_codes(session, user_id, codes)

    assert consume_recovery_code(session, user_id, codes[0]) is True
    assert consume_recovery_code(session, user_id, codes[0]) is False
```

- [ ] **Step 2: Run the auth tests to verify they fail**

Run: `pytest tests/test_password_policy.py tests/test_mfa.py tests/test_recovery_codes.py -v`
Expected: FAIL because validation and MFA services do not exist.

- [ ] **Step 3: Implement password validation, TOTP, QR, and recovery codes**

```python
def validate_password_strength(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long.")
    if password.lower() == password or password.upper() == password:
        errors.append("Password must mix character classes.")
    if not any(ch.isdigit() for ch in password):
        errors.append("Password must include a digit.")
    if password.isalnum():
        errors.append("Password must include a symbol.")
    return errors
```

```python
def build_totp_enrollment(login_name: str) -> TotpEnrollment:
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=login_name, issuer_name="CalSync")
    png_bytes = render_qr_png(uri)
    return TotpEnrollment(secret=secret, otpauth_uri=uri, qr_png_bytes=png_bytes)
```

- [ ] **Step 4: Encrypt TOTP secrets and hash recovery codes before persistence**

```python
encrypted_secret = encrypt_text(settings.encryption_key, enrollment.secret)
recovery_hash = pwd_context.hash(raw_code)
```

- [ ] **Step 5: Run the auth tests**

Run: `pytest tests/test_password_policy.py tests/test_mfa.py tests/test_recovery_codes.py -v`
Expected: PASS

- [ ] **Step 6: Commit the auth service layer**

```bash
git add src/calsync/crypto.py src/calsync/services/auth.py src/calsync/schemas/auth.py tests/test_password_policy.py tests/test_mfa.py tests/test_recovery_codes.py
git commit -m "feat: add password policy and MFA services"
```

## Task 5: Build First-Run Setup, Setup Lockout, And Login Flow

**Files:**
- Create: `C:\code\calsync\src\calsync\services\bootstrap.py`
- Create: `C:\code\calsync\src\calsync\web\deps.py`
- Create: `C:\code\calsync\src\calsync\web\routes\setup.py`
- Create: `C:\code\calsync\src\calsync\web\routes\auth.py`
- Create: `C:\code\calsync\src\calsync\web\templates\setup.html`
- Create: `C:\code\calsync\src\calsync\web\templates\login.html`
- Create: `C:\code\calsync\src\calsync\web\templates\mfa_challenge.html`
- Test: `C:\code\calsync\tests\test_setup_flow.py`
- Test: `C:\code\calsync\tests\test_auth_login.py`

- [ ] **Step 1: Write the failing first-run and login tests**

```python
def test_first_run_setup_creates_admin_and_locks_route(client):
    response = client.post("/setup", data={
        "username": "admin",
        "email": "admin@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "totp_code": generated_valid_code,
        "recovery_acknowledged": "true",
    })

    assert response.status_code == 303
    assert client.get("/setup").status_code == 404
```

```python
def test_login_requires_password_then_totp(client, admin_user):
    first = client.post("/login", data={"identifier": "admin", "password": "StrongPassword123!"})
    assert first.status_code == 303

    second = client.post("/login/mfa", data={"code": current_totp_code})
    assert second.status_code == 303
```

- [ ] **Step 2: Run the setup/auth tests to verify they fail**

Run: `pytest tests/test_setup_flow.py tests/test_auth_login.py -v`
Expected: FAIL because routes and setup state logic do not exist.

- [ ] **Step 3: Implement the first-run setup flow**

```python
if bootstrap_service.is_setup_complete(session):
    raise HTTPException(status_code=404)

enrollment = auth_service.build_totp_enrollment(form.login_name)
recovery_codes = auth_service.generate_recovery_codes()

if not auth_service.verify_totp(enrollment.secret, form.totp_code):
    return render_setup(errors=["Invalid MFA code."])

bootstrap_service.create_initial_admin(
    session=session,
    username=form.username,
    email=form.email,
    password=form.password,
    totp_secret=enrollment.secret,
    recovery_codes=recovery_codes,
)
```

- [ ] **Step 4: Implement password-plus-MFA login**

```python
user = auth_service.authenticate_password(session, identifier=form.identifier, password=form.password)
request.session["pending_mfa_user_id"] = str(user.id)

if auth_service.verify_totp_for_user(session, user, form.code) or auth_service.consume_recovery_code(session, user, form.code):
    request.session["admin_user_id"] = str(user.id)
    request.session.pop("pending_mfa_user_id", None)
```

- [ ] **Step 5: Run the setup/auth tests**

Run: `pytest tests/test_setup_flow.py tests/test_auth_login.py -v`
Expected: PASS

- [ ] **Step 6: Commit the setup and login flows**

```bash
git add src/calsync/services/bootstrap.py src/calsync/web/deps.py src/calsync/web/routes/setup.py src/calsync/web/routes/auth.py src/calsync/web/templates/setup.html src/calsync/web/templates/login.html src/calsync/web/templates/mfa_challenge.html tests/test_setup_flow.py tests/test_auth_login.py
git commit -m "feat: add first-run admin setup and mfa login"
```

## Task 6: Add Break-Glass CLI Resets And Session Protections

**Files:**
- Create: `C:\code\calsync\src\calsync\cli.py`
- Modify: `C:\code\calsync\src\calsync\services\bootstrap.py`
- Test: `C:\code\calsync\tests\test_cli_resets.py`

- [ ] **Step 1: Write the failing CLI reset tests**

```python
def test_reset_admin_password_preserves_provider_configuration(session, runner, seeded_state):
    result = runner.invoke(app, ["reset-admin-password", "--username", "admin", "--password", "NewStrongPassword123!"])

    assert result.exit_code == 0
    assert session.query(ProviderAccount).count() == seeded_state.provider_accounts
    assert session.query(PublishedFeed).count() == seeded_state.feed_count
```

```python
def test_reset_admin_mfa_clears_only_mfa_state(session, runner, admin_user):
    result = runner.invoke(app, ["reset-admin-mfa", "--username", "admin"])

    assert result.exit_code == 0
    session.refresh(admin_user)
    assert admin_user.mfa_enrolled is False
    assert admin_user.password_hash
```

- [ ] **Step 2: Run the CLI tests to verify they fail**

Run: `pytest tests/test_cli_resets.py -v`
Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement local-only reset commands**

```python
@app.command("reset-admin-password")
def reset_admin_password(username: str, password: str) -> None:
    bootstrap_service.reset_admin_password(session, username=username, new_password=password)
```

```python
@app.command("reset-admin-mfa")
def reset_admin_mfa(username: str) -> None:
    bootstrap_service.reset_admin_mfa(session, username=username)
```

- [ ] **Step 4: Ensure logs redact secret values and sessions are cleared after reset**

```python
logger.info("Reset admin password", extra={"username": username})
user.session_version += 1
```

- [ ] **Step 5: Run the CLI tests**

Run: `pytest tests/test_cli_resets.py -v`
Expected: PASS

- [ ] **Step 6: Commit the operator reset commands**

```bash
git add src/calsync/cli.py src/calsync/services/bootstrap.py tests/test_cli_resets.py
git commit -m "feat: add break-glass admin reset commands"
```

## Task 7: Implement Mock Provider Discovery, Normalization, And Sync Logging

**Files:**
- Create: `C:\code\calsync\src\calsync\services\providers\base.py`
- Create: `C:\code\calsync\src\calsync\services\providers\mock.py`
- Create: `C:\code\calsync\src\calsync\services\sync.py`
- Create: `C:\code\calsync\src\calsync\repos\providers.py`
- Create: `C:\code\calsync\src\calsync\schemas\providers.py`
- Test: `C:\code\calsync\tests\test_mock_provider.py`

- [ ] **Step 1: Write the failing mock-provider tests**

```python
def test_mock_provider_discovers_calendars(session):
    account = create_mock_provider_account(session)

    discovered = sync_service.discover_calendars(session, account.id)

    assert [calendar.name for calendar in discovered] == ["Home", "Work", "Shared"]
```

```python
def test_mock_sync_populates_events_without_duplicates(session, account):
    sync_service.sync_account(session, account.id)
    sync_service.sync_account(session, account.id)

    assert session.query(Event).count() == expected_mock_event_count
    assert session.query(SyncLog).count() == 2
```

- [ ] **Step 2: Run the mock-provider tests to verify they fail**

Run: `pytest tests/test_mock_provider.py -v`
Expected: FAIL because provider adapters and sync orchestration do not exist.

- [ ] **Step 3: Implement the provider adapter contract and deterministic mock provider**

```python
class ProviderAdapter(Protocol):
    provider_type: str

    def discover_calendars(self, account: ProviderAccount) -> list[DiscoveredCalendar]: ...
    def fetch_events(self, account: ProviderAccount, calendar: ProviderCalendar) -> list[NormalizedEvent]: ...
```

```python
class MockProviderAdapter:
    provider_type = "mock"

    def discover_calendars(self, account: ProviderAccount) -> list[DiscoveredCalendar]:
        return [
            DiscoveredCalendar(external_id="home", name="Home", timezone="America/Anchorage"),
            DiscoveredCalendar(external_id="work", name="Work", timezone="America/Anchorage"),
            DiscoveredCalendar(external_id="shared", name="Shared", timezone="UTC"),
        ]
```

- [ ] **Step 4: Implement sync logging and event upsert orchestration**

```python
with sync_log_repo.begin_run(session, account_id=account.id, trigger="manual") as sync_run:
    calendars = adapter.discover_calendars(account)
    for calendar in enabled_calendars:
        for event in adapter.fetch_events(account, calendar):
            event_service.upsert_event(session, event)
    sync_run.mark_success(event_count=imported_count)
```

- [ ] **Step 5: Run the mock-provider tests**

Run: `pytest tests/test_mock_provider.py -v`
Expected: PASS

- [ ] **Step 6: Commit provider mocking and sync orchestration**

```bash
git add src/calsync/services/providers/base.py src/calsync/services/providers/mock.py src/calsync/services/sync.py src/calsync/repos/providers.py src/calsync/schemas/providers.py tests/test_mock_provider.py
git commit -m "feat: add mock provider discovery and sync orchestration"
```

## Task 8: Implement ICS Publishing And Feed Token Rotation

**Files:**
- Create: `C:\code\calsync\src\calsync\services\publishing.py`
- Create: `C:\code\calsync\src\calsync\web\routes\feeds.py`
- Create: `C:\code\calsync\src\calsync\repos\publishing.py`
- Test: `C:\code\calsync\tests\test_ics_publishing.py`

- [ ] **Step 1: Write the failing ICS tests**

```python
def test_combined_feed_returns_calendar_payload(client, seeded_events, combined_feed_token):
    response = client.get(f"/feeds/combined/{combined_feed_token}.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in response.text
```

```python
def test_rotating_feed_token_invalidates_previous_token(session, publishing_service, combined_feed):
    old_token = combined_feed.token
    new_feed = publishing_service.rotate_token(session, combined_feed.id)

    assert new_feed.token != old_token
    assert publishing_service.resolve_token(session, old_token) is None
```

- [ ] **Step 2: Run the ICS tests to verify they fail**

Run: `pytest tests/test_ics_publishing.py -v`
Expected: FAIL because publishing services and routes do not exist.

- [ ] **Step 3: Implement feed token generation and ICS rendering**

```python
def generate_feed_token() -> str:
    return secrets.token_urlsafe(32)
```

```python
calendar = Calendar()
calendar.add("prodid", "-//CalSync//EN")
calendar.add("version", "2.0")
for event in events:
    calendar.add_component(build_ical_event(event))
return calendar.to_ical().decode("utf-8")
```

- [ ] **Step 4: Expose tokenized feed routes**

```python
@router.get("/feeds/combined/{token}.ics")
def combined_feed(token: str, session: SessionDep) -> Response:
    feed = publishing_service.resolve_combined_feed(session, token)
    return Response(content=publishing_service.render_combined_ics(session, feed), media_type="text/calendar; charset=utf-8")
```

- [ ] **Step 5: Run the ICS tests**

Run: `pytest tests/test_ics_publishing.py -v`
Expected: PASS

- [ ] **Step 6: Commit ICS publishing**

```bash
git add src/calsync/services/publishing.py src/calsync/web/routes/feeds.py src/calsync/repos/publishing.py tests/test_ics_publishing.py
git commit -m "feat: add read-only ics publishing and token rotation"
```

## Task 9: Build The Server-Rendered Admin UI And Protected Pages

**Files:**
- Create: `C:\code\calsync\src\calsync\web\routes\dashboard.py`
- Create: `C:\code\calsync\src\calsync\web\routes\calendars.py`
- Create: `C:\code\calsync\src\calsync\web\routes\sync.py`
- Create: `C:\code\calsync\src\calsync\web\templates\base.html`
- Create: `C:\code\calsync\src\calsync\web\templates\dashboard.html`
- Create: `C:\code\calsync\src\calsync\web\templates\calendars.html`
- Create: `C:\code\calsync\src\calsync\web\templates\sync_status.html`
- Create: `C:\code\calsync\src\calsync\web\templates\ics_publishing.html`
- Create: `C:\code\calsync\src\calsync\web\static\app.css`
- Test: `C:\code\calsync\tests\test_dashboard_pages.py`

- [ ] **Step 1: Write the failing protected-page tests**

```python
def test_dashboard_requires_authenticated_admin(client):
    response = client.get("/admin")
    assert response.status_code == 303


def test_dashboard_shows_feed_links_and_sync_summary(authenticated_client, seeded_state):
    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Combined feed" in response.text
    assert "Last sync" in response.text
```

- [ ] **Step 2: Run the dashboard tests to verify they fail**

Run: `pytest tests/test_dashboard_pages.py -v`
Expected: FAIL because protected routes and templates do not exist.

- [ ] **Step 3: Implement authenticated dashboard, calendars, and sync-status routes**

```python
@router.get("/admin")
def dashboard(request: Request, session: SessionDep, current_admin: AdminUser = Depends(require_admin)):
    context = dashboard_service.build_context(session)
    return templates.TemplateResponse("dashboard.html", {"request": request, **context})
```

- [ ] **Step 4: Add template navigation and form flows for calendar enable/group and token rotation**

```html
<form method="post" action="/admin/calendars/{{ calendar.id }}/toggle">
  <button type="submit">{{ "Disable" if calendar.enabled else "Enable" }}</button>
</form>
```

- [ ] **Step 5: Run the dashboard tests**

Run: `pytest tests/test_dashboard_pages.py -v`
Expected: PASS

- [ ] **Step 6: Commit the Phase 1 admin UI**

```bash
git add src/calsync/web/routes/dashboard.py src/calsync/web/routes/calendars.py src/calsync/web/routes/sync.py src/calsync/web/templates src/calsync/web/static/app.css tests/test_dashboard_pages.py
git commit -m "feat: add phase 1 admin dashboard and calendar pages"
```

## Task 10: Add The Worker Role, Docker Compose, And Health-Checked Deployment

**Files:**
- Create: `C:\code\calsync\Dockerfile`
- Create: `C:\code\calsync\docker-compose.yml`
- Create: `C:\code\calsync\src\calsync\worker.py`
- Modify: `C:\code\calsync\.env.example`
- Test: `C:\code\calsync\tests\test_worker_config.py`

- [ ] **Step 1: Write the failing worker/deployment tests**

```python
def test_worker_uses_same_settings_defaults():
    settings = Settings.model_validate({})
    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 3080
```

```python
def test_env_example_documents_port_override():
    content = Path(".env.example").read_text()
    assert "APP_HOST=0.0.0.0" in content
    assert "APP_PORT=3080" in content
```

- [ ] **Step 2: Run the worker/deployment tests to verify they fail**

Run: `pytest tests/test_worker_config.py -v`
Expected: FAIL because worker wiring and `.env.example` are incomplete.

- [ ] **Step 3: Implement the worker entrypoint and Docker image**

```python
def main() -> None:
    settings = get_settings()
    logger.info("Starting CalSync worker", extra={"sync_poll_seconds": settings.sync_poll_seconds})
    run_worker_loop()
```

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .
CMD ["uv", "run", "uvicorn", "calsync.main:app", "--host", "0.0.0.0", "--port", "3080"]
```

- [ ] **Step 4: Add Compose services and healthchecks**

```yaml
services:
  web:
    build: .
    env_file: .env
    ports:
      - "${APP_PORT:-3080}:${APP_PORT:-3080}"
    command: uv run uvicorn calsync.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-3080}
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${APP_PORT:-3080}/healthz')\""]
```

- [ ] **Step 5: Run the worker/deployment tests**

Run: `pytest tests/test_worker_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit deployment wiring**

```bash
git add Dockerfile docker-compose.yml src/calsync/worker.py .env.example tests/test_worker_config.py
git commit -m "feat: add worker role and docker compose deployment"
```

## Task 11: Write The README, Ops Docs, Prompt Capture, And End-To-End Verification

**Files:**
- Modify: `C:\code\calsync\README.md`
- Create: `C:\code\calsync\docs\ops.md`
- Create: `C:\code\calsync\docs\prompts\backend.md`
- Test: `C:\code\calsync\tests\test_docs.py`

- [ ] **Step 1: Write the missing-docs checklist into tests or a docs audit helper**

```python
def test_readme_mentions_required_operator_topics():
    content = Path("README.md").read_text(encoding="utf-8")
    for phrase in [
        "APP_HOST=0.0.0.0",
        "APP_PORT=3080",
        "first-run admin setup",
        "MFA",
        "recovery codes",
        "reset-admin-password",
        "reset-admin-mfa",
        "backup",
        "known limitations",
    ]:
        assert phrase in content
```

- [ ] **Step 2: Run the docs test to verify it fails**

Run: `pytest tests/test_docs.py -v`
Expected: FAIL because the README and docs are incomplete.

- [ ] **Step 3: Write operator documentation and prompt-capture docs**

```md
# CalSync

## Docker deployment

1. Copy `.env.example` to `.env`
2. Set `APP_HOST=0.0.0.0`
3. Set `APP_PORT=3080` or another port
4. Run `docker compose up --build`
```

```md
# Backend Prompt Capture

- Issue: #1
- Scope: Phase 1 read-only aggregation foundation
- Behavioral requirements: mandatory MFA, no default admin, LAN binding, tokenized ICS, mock provider mode
```

- [ ] **Step 4: Run the full verification suite and compose smoke checks**

Run: `pytest -v`
Expected: PASS

Run: `docker compose config`
Expected: PASS with `web`, `worker`, and `db` services resolved.

Run: `docker compose up --build -d`
Expected: containers start successfully.

Run: `docker compose ps`
Expected: `web`, `worker`, and `db` are running or healthy.

Run: `curl http://localhost:3080/healthz`
Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit docs and validation updates**

```bash
git add README.md docs/ops.md docs/prompts/backend.md tests/test_docs.py
git commit -m "docs: add phase 1 deployment and operations guide"
```

- [ ] **Step 6: Update GitHub issue #1 with validation evidence and final scope notes**

```text
Validated:
- first-run setup lockout
- MFA enrollment and recovery codes
- mock provider discovery and sync
- combined/group/source ICS feeds
- docker compose deployment on port 3080
```

## Task 12: Final Repository Verification, Push, And Remote Confirmation

**Files:**
- Modify: `C:\code\calsync\README.md`
- Modify: `C:\code\calsync\docs\ops.md`
- Modify: `C:\code\calsync\docs\prompts\backend.md`

- [ ] **Step 1: Run the required git state commands**

Run: `git status --short`
Expected: clean working tree or only intentional final changes.

Run: `git branch --show-current`
Expected: `main`

Run: `git remote -v`
Expected: `origin` points at `https://github.com/NeonButrfly/calsync.git`

Run: `git log --oneline -5`
Expected: recent implementation commits are visible.

- [ ] **Step 2: Run final verification again before claiming completion**

Run: `pytest -v`
Expected: PASS

Run: `docker compose up --build -d`
Expected: PASS

Run: `curl http://localhost:3080/healthz`
Expected: PASS

- [ ] **Step 3: Create the final feature commit**

```bash
git add .
git commit -m "feat: build phase 1 calendar aggregation foundation"
```

- [ ] **Step 4: Push to remote main**

Run: `git push origin HEAD:main`
Expected: PASS

- [ ] **Step 5: Verify local HEAD matches remote main**

Run: `git fetch --prune origin "+refs/heads/main:refs/remotes/origin/main"`
Expected: PASS

Run: `git rev-parse HEAD`
Expected: returns local feature commit SHA.

Run: `git ls-remote origin refs/heads/main`
Expected: returns the same SHA as local `HEAD`.

- [ ] **Step 6: Update issue #1 and close it only if all acceptance criteria are actually verified**

```text
Completion evidence:
- Pre-change snapshot commit recorded
- Final implementation commit pushed to origin/main
- Local HEAD matches remote main
- Acceptance criteria verified with tests and Docker smoke checks
```

## Self-Review

### Spec coverage

- Runtime defaults and LAN binding: covered in Tasks 2, 10, and 11.
- First-run setup and mandatory MFA: covered in Tasks 4 and 5.
- Recovery codes and break-glass resets: covered in Tasks 4 and 6.
- Mock provider mode, normalization, and duplicate prevention: covered in Tasks 3 and 7.
- Combined/source/group ICS feeds: covered in Task 8.
- Server-rendered admin UI and sync status: covered in Task 9.
- Worker container shape and persistence: covered in Task 10.
- Documentation, prompt capture, and validation: covered in Task 11.
- Final git/push/remote verification requirements: covered in Task 12.

### Placeholder scan

- No `TODO`, `TBD`, or deferred “implement later” steps remain in the plan.
- Every task names exact files, verification commands, and commit messages.

### Type consistency

- The plan consistently uses `Settings`, `ProviderAccount`, `ProviderCalendar`, `Event`, `PublishedFeed`, and `SyncLog`.
- Auth behavior consistently uses password-first, MFA-second login and a locked first-run setup flow.
