# CalSync Utility Expansion Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first trust-and-cleanup slice for CalSync so removed or cancelled upstream events stop polluting active views, duplicate calendar entries are grouped conservatively, and admin views plus ICS output reflect canonical active schedule data.

**Architecture:** Extend the existing normalized `events` model with lifecycle metadata and then add a lightweight canonical grouping layer on top. Keep Google and iCloud adapters read-only, push trust decisions into shared sync and reconciliation services, and make the UI plus ICS read from filtered active/canonical event queries instead of blindly rendering every raw provider event.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, PostgreSQL/SQLite test compatibility, Jinja templates, pytest

---

## File Structure

### Existing files to modify

- `src/calsync/models/events.py`
  - extend the `Event` model with lifecycle and reconciliation fields
- `src/calsync/repos/events.py`
  - support event upsert, stale marking, and canonical-group writes
- `src/calsync/repos/providers.py`
  - expose queries needed for full-calendar reconciliation
- `src/calsync/services/sync.py`
  - mark provider-missing events stale or deleted during sync runs
- `src/calsync/services/providers/google.py`
  - preserve deleted-event semantics in normalized events
- `src/calsync/services/providers/icloud.py`
  - preserve cancellation and disappearance semantics for CalDAV events
- `src/calsync/services/publishing.py`
  - publish only active canonical events in ICS feeds
- `src/calsync/web/routes/dashboard.py`
  - query canonical active events and trust metrics
- `src/calsync/web/routes/feeds.py`
  - emit filtered canonical event sets
- `src/calsync/web/routes/calendars.py`
  - display grouped event status or duplicate indicators where needed
- `src/calsync/web/templates/dashboard.html`
  - show stale cleanup and duplicate-review summary cards
- `src/calsync/web/templates/sync_status.html`
  - show lifecycle reconciliation counts
- `README.md`
  - document trust-and-cleanup behavior
- `docs/ops.md`
  - document reconciliation and cleanup expectations
- `docs/prompts/backend.md`
  - capture the shipped Phase A behavior

### New files to create

- `alembic/versions/<timestamp>_event_trust_and_groups.py`
  - schema migration for lifecycle fields and event-group tables
- `src/calsync/models/reconciliation.py`
  - `EventGroup` and `EventGroupMember` models
- `src/calsync/services/reconciliation.py`
  - duplicate detection and canonical grouping logic
- `tests/test_event_lifecycle.py`
  - stale, deleted, and cancelled event reconciliation coverage
- `tests/test_event_reconciliation.py`
  - duplicate grouping and canonical selection coverage
- `tests/test_dashboard_trust_metrics.py`
  - dashboard trust summary rendering
- `tests/test_ics_publishing.py`
  - canonical/active feed behavior coverage

### Boundaries to preserve

- Do not add write-back logic anywhere.
- Do not add Athena or message-derived connectors in Phase A.
- Keep the grouping rules conservative and deterministic:
  - exact provider identity still owns raw upsert semantics
  - cross-source grouping only applies after raw events exist

---

### Task 1: Add Event Lifecycle Schema

**Files:**
- Create: `alembic/versions/<timestamp>_event_trust_and_groups.py`
- Create: `src/calsync/models/reconciliation.py`
- Modify: `src/calsync/models/events.py`
- Modify: `src/calsync/models/__init__.py`
- Test: `tests/test_event_lifecycle.py`

- [ ] **Step 1: Write the failing lifecycle schema test**

```python
def test_event_lifecycle_fields_round_trip(migrated_session_factory):
    from calsync.models import Event
    from calsync.repos.events import upsert_event

    payload = {
        "provider_type": "mock",
        "provider_account_id": "acct-1",
        "provider_calendar_id": "cal-1",
        "provider_event_id": "evt-1",
        "title": "Dental Cleaning",
        "starts_at": datetime(2026, 5, 22, 18, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 5, 22, 19, 0, tzinfo=UTC),
        "all_day": False,
        "status": "confirmed",
        "event_visibility_state": "active",
        "source_payload": {"provider": "mock"},
    }

    with migrated_session_factory() as session:
        event = upsert_event(session, payload)
        session.commit()
        event_id = event.id

    with migrated_session_factory() as session:
        reloaded = session.get(Event, event_id)
        assert reloaded is not None
        assert reloaded.event_visibility_state == "active"
        assert reloaded.removed_upstream_at is None
        assert reloaded.last_seen_upstream_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_event_lifecycle.py::test_event_lifecycle_fields_round_trip -v`
Expected: FAIL because the new fields and migration do not exist yet.

- [ ] **Step 3: Write the migration and model changes**

```python
class Event(Base):
    __tablename__ = "events"

    event_visibility_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
    last_seen_upstream_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    removed_upstream_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    canonical_group_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("event_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
```

```python
class EventGroup(Base):
    __tablename__ = "event_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    display_title: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_starts_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    preferred_ends_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    preferred_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_event_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_event_lifecycle.py::test_event_lifecycle_fields_round_trip tests/test_event_normalization.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alembic src/calsync/models tests/test_event_lifecycle.py
git commit -m "feat: add event lifecycle schema"
```

### Task 2: Reconcile Removed And Cancelled Upstream Events

**Files:**
- Modify: `src/calsync/repos/events.py`
- Modify: `src/calsync/services/sync.py`
- Modify: `src/calsync/services/providers/google.py`
- Modify: `src/calsync/services/providers/icloud.py`
- Test: `tests/test_event_lifecycle.py`

- [ ] **Step 1: Write the failing cleanup tests**

```python
def test_sync_marks_provider_missing_events_removed(migrated_session, settings):
    stale = upsert_event(migrated_session, make_event(provider_event_id="evt-stale"))
    current = upsert_event(migrated_session, make_event(provider_event_id="evt-current"))
    migrated_session.commit()

    mark_events_missing_from_sync(
        migrated_session,
        provider_type="mock",
        provider_account_id="acct-1",
        provider_calendar_id="cal-1",
        seen_provider_event_ids={"evt-current"},
    )

    migrated_session.refresh(stale)
    migrated_session.refresh(current)
    assert stale.event_visibility_state == "deleted_upstream"
    assert stale.removed_upstream_at is not None
    assert current.event_visibility_state == "active"
```

```python
def test_cancelled_events_are_not_left_active(migrated_session):
    event = upsert_event(migrated_session, make_event(status="cancelled"))
    assert event.event_visibility_state == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_lifecycle.py -k "missing_events_removed or cancelled_events_are_not_left_active" -v`
Expected: FAIL because sync and upsert do not apply lifecycle transitions yet.

- [ ] **Step 3: Implement lifecycle reconciliation**

```python
def upsert_event(session: Session, normalized_event: Mapping[str, Any]) -> Event:
    normalized_status = str(normalized_event.get("status", "confirmed"))
    visibility_state = "cancelled" if normalized_status == "cancelled" else "active"
    now = utcnow()
    ...
    event.status = normalized_status
    event.event_visibility_state = visibility_state
    event.last_seen_upstream_at = now
    if visibility_state == "active":
        event.removed_upstream_at = None
```

```python
def mark_events_missing_from_sync(
    session: Session,
    *,
    provider_type: str,
    provider_account_id: str,
    provider_calendar_id: str,
    seen_provider_event_ids: set[str],
) -> int:
    events = session.scalars(
        select(Event).where(
            Event.provider_type == provider_type,
            Event.provider_account_id == provider_account_id,
            Event.provider_calendar_id == provider_calendar_id,
        )
    ).all()
    marked = 0
    for event in events:
        if event.provider_event_id not in seen_provider_event_ids:
            event.event_visibility_state = "deleted_upstream"
            event.removed_upstream_at = utcnow()
            marked += 1
    session.flush()
    return marked
```

- [ ] **Step 4: Wire lifecycle reconciliation into sync**

```python
seen_ids: set[str] = set()
for event in adapter.fetch_events(account, calendar):
    seen_ids.add(event.provider_event_id)
    upsert_event(session, event.model_dump(mode="python"))

mark_events_missing_from_sync(
    session,
    provider_type=account.provider_type,
    provider_account_id=account.provider_account_id,
    provider_calendar_id=calendar.provider_calendar_id,
    seen_provider_event_ids=seen_ids,
)
```

- [ ] **Step 5: Run targeted tests**

Run: `pytest tests/test_event_lifecycle.py tests/test_google_provider.py tests/test_icloud_provider.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/calsync/repos/events.py src/calsync/services/sync.py src/calsync/services/providers/google.py src/calsync/services/providers/icloud.py tests/test_event_lifecycle.py
git commit -m "feat: reconcile removed and cancelled events"
```

### Task 3: Add Conservative Duplicate Grouping

**Files:**
- Create: `src/calsync/services/reconciliation.py`
- Modify: `src/calsync/repos/events.py`
- Test: `tests/test_event_reconciliation.py`

- [ ] **Step 1: Write the failing duplicate-group tests**

```python
def test_reconciliation_groups_same_time_and_title_events(migrated_session):
    google = upsert_event(migrated_session, make_event(
        provider_type="google",
        provider_account_id="g-1",
        provider_calendar_id="cal-a",
        provider_event_id="evt-1",
        title="Cardiology Follow-up",
    ))
    icloud = upsert_event(migrated_session, make_event(
        provider_type="icloud_caldav",
        provider_account_id="i-1",
        provider_calendar_id="cal-b",
        provider_event_id="evt-2",
        title="Cardiology Follow-up",
    ))

    groups = reconcile_event_groups(migrated_session)

    migrated_session.refresh(google)
    migrated_session.refresh(icloud)
    assert len(groups) == 1
    assert google.canonical_group_id == icloud.canonical_group_id
```

```python
def test_reconciliation_does_not_group_far_apart_events(migrated_session):
    early = upsert_event(migrated_session, make_event(title="Checkup", starts_at=datetime(2026, 6, 1, 17, 0, tzinfo=UTC), ends_at=datetime(2026, 6, 1, 18, 0, tzinfo=UTC)))
    late = upsert_event(migrated_session, make_event(provider_event_id="evt-2", title="Checkup", starts_at=datetime(2026, 6, 2, 17, 0, tzinfo=UTC), ends_at=datetime(2026, 6, 2, 18, 0, tzinfo=UTC)))

    groups = reconcile_event_groups(migrated_session)

    assert groups == []
    assert early.canonical_group_id is None
    assert late.canonical_group_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_event_reconciliation.py -v`
Expected: FAIL because no grouping service exists yet.

- [ ] **Step 3: Implement minimal conservative grouping**

```python
def reconcile_event_groups(session: Session) -> list[EventGroup]:
    active_events = session.scalars(
        select(Event).where(Event.event_visibility_state == "active")
    ).all()
    grouped: list[EventGroup] = []
    buckets: dict[tuple[str, datetime], list[Event]] = {}

    for event in active_events:
        key = (normalize_title(event.title), event.starts_at)
        buckets.setdefault(key, []).append(event)

    for candidates in buckets.values():
        distinct_sources = {candidate.provider_type for candidate in candidates}
        if len(candidates) < 2 or len(distinct_sources) < 2:
            continue
        group = create_or_replace_event_group(session, candidates)
        grouped.append(group)
    return grouped
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_event_reconciliation.py tests/test_event_normalization.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/reconciliation.py src/calsync/repos/events.py tests/test_event_reconciliation.py
git commit -m "feat: add conservative duplicate grouping"
```

### Task 4: Filter Admin Views And ICS To Active Canonical Events

**Files:**
- Modify: `src/calsync/services/publishing.py`
- Modify: `src/calsync/web/routes/dashboard.py`
- Modify: `src/calsync/web/routes/feeds.py`
- Modify: `src/calsync/web/templates/dashboard.html`
- Modify: `src/calsync/web/templates/sync_status.html`
- Test: `tests/test_ics_publishing.py`
- Test: `tests/test_dashboard_trust_metrics.py`

- [ ] **Step 1: Write the failing presentation tests**

```python
def test_combined_ics_excludes_deleted_upstream_events(client, session):
    active = seed_event(session, provider_event_id="evt-live", event_visibility_state="active")
    deleted = seed_event(session, provider_event_id="evt-old", event_visibility_state="deleted_upstream")

    response = client.get("/feeds/combined.ics?token=test-token")

    assert response.status_code == 200
    assert "evt-live" in response.text
    assert "evt-old" not in response.text
```

```python
def test_dashboard_shows_trust_summary(client, authed_session):
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Stale cleanup" in response.text
    assert "Duplicate groups" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ics_publishing.py tests/test_dashboard_trust_metrics.py -v`
Expected: FAIL because feeds and dashboard still render raw unfiltered behavior.

- [ ] **Step 3: Implement active canonical queries**

```python
def list_publishable_events(session: Session) -> list[Event]:
    return session.scalars(
        select(Event).where(Event.event_visibility_state == "active")
        .order_by(Event.starts_at.asc())
    ).all()
```

```python
def dashboard_summary(session: Session) -> dict[str, int]:
    return {
        "deleted_upstream": count_events_by_visibility(session, "deleted_upstream"),
        "cancelled": count_events_by_visibility(session, "cancelled"),
        "duplicate_groups": count_event_groups(session),
    }
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_ics_publishing.py tests/test_dashboard_trust_metrics.py tests/test_dashboard_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/publishing.py src/calsync/web/routes/dashboard.py src/calsync/web/routes/feeds.py src/calsync/web/templates/dashboard.html src/calsync/web/templates/sync_status.html tests/test_ics_publishing.py tests/test_dashboard_trust_metrics.py
git commit -m "feat: filter active canonical events in views and feeds"
```

### Task 5: Document And Verify Phase A

**Files:**
- Modify: `README.md`
- Modify: `docs/ops.md`
- Modify: `docs/prompts/backend.md`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write the failing docs assertions**

```python
def test_docs_cover_event_cleanup_and_duplicate_grouping():
    readme = Path("README.md").read_text(encoding="utf-8")
    ops = Path("docs/ops.md").read_text(encoding="utf-8")
    backend = Path("docs/prompts/backend.md").read_text(encoding="utf-8")

    assert "deleted_upstream" in readme
    assert "duplicate groups" in ops
    assert "#11" in backend
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_docs.py -v`
Expected: FAIL because the new trust-and-cleanup behavior is not documented yet.

- [ ] **Step 3: Update operator docs**

```markdown
## Event Trust And Cleanup

- CalSync marks upstream-missing events as `deleted_upstream`
- cancelled events are excluded from active calendar and ICS views
- conservative duplicate grouping can collapse obvious cross-source duplicates into canonical appointments while preserving source provenance
```

- [ ] **Step 4: Run full verification**

Run: `pytest -v`
Expected: PASS

Run: `docker compose config`
Expected: config renders successfully

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ops.md docs/prompts/backend.md tests/test_docs.py
git commit -m "docs: capture phase a trust and cleanup behavior"
```

### Task 6: Deployment Verification And Tracking Closure

**Files:**
- Modify: GitHub issue `#11`

- [ ] **Step 1: Push the completed branch tip**

Run: `git push origin HEAD:main`
Expected: remote accepts the new tip

- [ ] **Step 2: Verify remote main matches**

Run: `git fetch --prune origin "+refs/heads/main:refs/remotes/origin/main"`
Expected: fetch succeeds

Run:

```powershell
$LOCAL_HEAD=(git rev-parse HEAD).Trim()
$REMOTE_MAIN=(git ls-remote origin refs/heads/main | ForEach-Object { ($_ -split "`t")[0] }).Trim()
Write-Output "LOCAL_HEAD=$LOCAL_HEAD"
Write-Output "REMOTE_MAIN=$REMOTE_MAIN"
```

Expected: the two SHAs match

- [ ] **Step 3: Redeploy and verify on the Pi**

Run:

```powershell
ssh kay@192.168.50.232 "cd ~/apps/calsync && git fetch origin && git checkout main && git reset --hard $LOCAL_HEAD && docker compose up --build -d"
```

Expected: stack rebuilds successfully

Run:

```powershell
Invoke-WebRequest -UseBasicParsing https://calsync.neonbutterfly.net/healthz
```

Expected: HTTP 200 with `{\"status\":\"ok\"}`

- [ ] **Step 4: Update issue `#11` with evidence**

```markdown
- trust-and-cleanup Phase A implemented
- lifecycle reconciliation verified
- duplicate grouping verified
- dashboard and ICS filtering verified
- Pi deployment and public health confirmed
```

- [ ] **Step 5: Close issue if verified**

Close only if:
- tests passed
- deployment is healthy
- docs match shipped behavior

Otherwise leave it open with blocker details.
