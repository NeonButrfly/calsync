# Problem Inbox Actions And Event Explain View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add richer direct actions to `/admin/problems` and a new `/admin/events/{event_id}` explain page so operators can understand and fix duplicate/trust issues without hunting across the app.

**Architecture:** Extend the existing problem-detection service so duplicate problems carry actionable event metadata, then add one explain-view service and private event route that reuse current reconciliation and sync state instead of inventing a second trust model. Keep the inbox action-first, and use the explain page as the deeper inspection surface.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Jinja templates, pytest, Docker Compose

---

## File Structure

- `src/calsync/services/problems.py`
  - Extend problem items with event-aware duplicate actions and explain links.
- `src/calsync/services/reconciliation.py`
  - Add lightweight helpers to load grouped event copies for one event without duplicating grouping logic in routes.
- `src/calsync/services/event_explain.py`
  - New focused service that builds one operator-facing event explanation view model.
- `src/calsync/web/routes/problems.py`
  - Add richer duplicate action handlers that map to existing reconciliation operations.
- `src/calsync/web/routes/events.py`
  - New private explain-page route for one event.
- `src/calsync/web/routes/__init__.py`
  - Register the new event route.
- `src/calsync/web/templates/problems.html`
  - Render richer duplicate action buttons and explain links.
- `src/calsync/web/templates/event_explain.html`
  - New private event explanation template.
- `src/calsync/web/static/app.css`
  - Shared styling for explain sections and denser problem-card action rows.
- `tests/test_problem_pages.py`
  - Add inbox action coverage for provider-aware duplicate actions.
- `tests/test_event_explain_page.py`
  - New page-level tests for explain rendering and event actions.
- `README.md`
  - Document the new explain route and richer inbox flow.
- `docs/ops.md`
  - Document operator usage and verification points.
- `docs/prompts/backend.md`
  - Capture the implemented behavior for issue `#15`.

---

### Task 1: Extend Problem Models For Provider-Aware Duplicate Actions

**Files:**
- Modify: `src/calsync/services/problems.py`
- Modify: `src/calsync/services/reconciliation.py`
- Test: `tests/test_problem_pages.py`

- [ ] **Step 1: Write the failing tests for richer duplicate actions**

```python
def test_problem_page_lists_provider_specific_duplicate_actions(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "Keep Google copy" in response.text
    assert "Keep iCloud copy" in response.text
    assert "Show both" in response.text
    assert "Explain this event" in response.text
```

```python
def test_problem_page_hides_provider_specific_action_when_provider_copy_missing(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            google_copy = session.scalar(select(Event).where(Event.provider_type == "google"))
            assert google_copy is not None
            session.delete(google_copy)
            rebuild_duplicate_groups(session)
            session.commit()

        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "Keep Google copy" not in response.text
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_problem_pages.py -k "provider_specific_duplicate_actions or provider_specific_action_when_provider_copy_missing" -v
```

Expected:

- FAIL because the inbox currently only renders a single `Review duplicates` action and has no provider-aware duplicate buttons

- [ ] **Step 3: Extend `ProblemItem` and duplicate-problem assembly with structured event actions**

Add focused fields to `src/calsync/services/problems.py`:

```python
@dataclass
class ProblemAction:
    label: str
    target: str
    method: str = "get"


@dataclass
class ProblemItem:
    id: str
    category: str
    severity: str
    title: str
    summary: str
    source_label: str
    primary_action: ProblemAction
    secondary_action: ProblemAction | None = None
    extra_actions: list[ProblemAction] | None = None
    event_id: str | None = None
```

Build duplicate actions using grouped event copies:

```python
def _duplicate_problem_actions(duplicate_group: DuplicateGroupView) -> list[ProblemAction]:
    actions: list[ProblemAction] = [
        ProblemAction(
            label="Keep preferred copy",
            target=f"/admin/review#group-{duplicate_group.group.id}",
        ),
        ProblemAction(
            label="Show both",
            target=f"/admin/events/{duplicate_group.group.preferred_event_id}",
        ),
        ProblemAction(
            label="Explain this event",
            target=f"/admin/events/{duplicate_group.group.preferred_event_id}",
        ),
    ]
    if any(event.provider_type == "google" for event in duplicate_group.events):
        actions.insert(
            1,
            ProblemAction(
                label="Keep Google copy",
                target=f"/admin/problems/actions/group/{duplicate_group.group.id}/provider/google",
                method="post",
            ),
        )
    if any(event.provider_type == "icloud_caldav" for event in duplicate_group.events):
        actions.insert(
            1,
            ProblemAction(
                label="Keep iCloud copy",
                target=f"/admin/problems/actions/group/{duplicate_group.group.id}/provider/icloud_caldav",
                method="post",
            ),
        )
    return actions
```

Add one small reconciliation helper in `src/calsync/services/reconciliation.py`:

```python
def list_group_events(session: Session, group_id: str) -> list[Event]:
    return session.scalars(
        select(Event)
        .where(Event.canonical_group_id == group_id)
        .order_by(Event.starts_at, Event.provider_type, Event.provider_account_id, Event.provider_event_id)
    ).all()
```

- [ ] **Step 4: Update the inbox template to render the extra actions**

Modify `src/calsync/web/templates/problems.html` so duplicate problems can render several action buttons:

```html
{% if problem.extra_actions %}
  {% for action in problem.extra_actions %}
    {% if action.method == "post" %}
    <form method="post" action="{{ action.target }}">
      <button type="submit" class="secondary-button">{{ action.label }}</button>
    </form>
    {% else %}
    <a class="button-link button-link--secondary" href="{{ action.target }}">{{ action.label }}</a>
    {% endif %}
  {% endfor %}
{% endif %}
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```bash
pytest tests/test_problem_pages.py -k "provider_specific_duplicate_actions or provider_specific_action_when_provider_copy_missing" -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add src/calsync/services/problems.py src/calsync/services/reconciliation.py src/calsync/web/templates/problems.html tests/test_problem_pages.py
git commit -m "feat: add provider-aware problem inbox actions"
```

---

### Task 2: Add Duplicate Fix Actions To The Problem Inbox

**Files:**
- Modify: `src/calsync/web/routes/problems.py`
- Modify: `src/calsync/services/reconciliation.py`
- Test: `tests/test_problem_pages.py`

- [ ] **Step 1: Write the failing action tests**

```python
def test_problem_page_can_keep_google_copy(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            group = list_duplicate_groups(session)[0]
            google_copy = next(event for event in group.events if event.provider_type == "google")

        response = client.post(
            f"/admin/problems/actions/group/{group.group.id}/provider/google",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/problems"

        with _db_session(client) as session:
            refreshed_group = list_duplicate_groups(session)[0]
            assert refreshed_group.group.preferred_event_id == google_copy.id
```

```python
def test_problem_page_can_restore_both_duplicate_copies(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            group = list_duplicate_groups(session)[0]

        response = client.post(
            f"/admin/problems/actions/group/{group.group.id}/show-both",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/problems"

        with _db_session(client) as session:
            refreshed = list_group_events(session, group.group.id)
            assert all(event.event_visibility_state == "active" for event in refreshed)
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_problem_pages.py -k "keep_google_copy or restore_both_duplicate_copies" -v
```

Expected:

- FAIL because the inbox route currently exposes only sync actions

- [ ] **Step 3: Implement provider-keep and show-both action handlers**

Add routes in `src/calsync/web/routes/problems.py`:

```python
@router.post("/actions/group/{group_id}/provider/{provider_type}")
def keep_provider_copy(
    group_id: str,
    provider_type: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    events = list_group_events(session, group_id)
    selected = next((event for event in events if event.provider_type == provider_type), None)
    if selected is None:
        raise HTTPException(status_code=404, detail="Requested provider copy not found.")
    prefer_event_in_group(session, group_id, selected.id)
    session.commit()
    return RedirectResponse(url="/admin/problems", status_code=303)
```

```python
@router.post("/actions/group/{group_id}/show-both")
def show_both_group_copies(
    group_id: str,
    session: Session = Depends(get_db),
    _: AdminUser = Depends(require_admin),
):
    events = list_group_events(session, group_id)
    if not events:
        raise HTTPException(status_code=404, detail="Duplicate group not found.")
    for event in events:
        if event.event_visibility_state == "hidden_duplicate":
            restore_hidden_duplicate(session, event.id)
    session.commit()
    return RedirectResponse(url="/admin/problems", status_code=303)
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```bash
pytest tests/test_problem_pages.py -k "keep_google_copy or restore_both_duplicate_copies" -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/routes/problems.py src/calsync/services/reconciliation.py tests/test_problem_pages.py
git commit -m "feat: add direct duplicate fix actions"
```

---

### Task 3: Add The Event Explain Service And Private Event Route

**Files:**
- Create: `src/calsync/services/event_explain.py`
- Create: `src/calsync/web/routes/events.py`
- Modify: `src/calsync/web/routes/__init__.py`
- Create: `src/calsync/web/templates/event_explain.html`
- Test: `tests/test_event_explain_page.py`

- [ ] **Step 1: Write the failing explain-page tests**

```python
def test_event_explain_page_requires_authenticated_admin(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        response = client.get("/admin/events/example-id", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
```

```python
def test_event_explain_page_shows_grouped_copies_and_preferred_state(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)

        with _db_session(client) as session:
            group = list_duplicate_groups(session)[0]
            preferred = next(event for event in group.events if event.id == group.group.preferred_event_id)

        response = client.get(f"/admin/events/{preferred.id}")

    assert response.status_code == 200
    assert "Why CalSync is showing this appointment" in response.text
    assert "Preferred copy" in response.text
    assert "Grouped source copies" in response.text
    assert "google" in response.text.lower()
    assert "icloud" in response.text.lower()
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_event_explain_page.py -v
```

Expected:

- FAIL because the route, service, and template do not exist yet

- [ ] **Step 3: Create the explain view model service**

Create `src/calsync/services/event_explain.py`:

```python
@dataclass
class EventExplainCopy:
    id: str
    title: str
    provider_type: str
    provider_account_id: str
    provider_calendar_id: str
    visibility_state: str
    is_preferred: bool


@dataclass
class EventExplainView:
    event: Event
    copies: list[EventExplainCopy]
    preferred_reason: str
    latest_sync: SyncLog | None
```

```python
def build_event_explain_view(session: Session, event_id: str) -> EventExplainView:
    event = session.get(Event, event_id)
    if event is None:
        raise LookupError(f"Event not found: {event_id}")

    group = session.get(EventGroup, event.canonical_group_id) if event.canonical_group_id else None
    copies = (
        list_group_events(session, event.canonical_group_id)
        if event.canonical_group_id
        else [event]
    )
    latest_sync = session.scalar(
        select(SyncLog)
        .where(
            SyncLog.provider_type == event.provider_type,
            SyncLog.account.has(ProviderAccount.provider_account_id == event.provider_account_id),
        )
        .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
    )
    return EventExplainView(
        event=event,
        copies=[
            EventExplainCopy(
                id=copy.id,
                title=copy.title,
                provider_type=copy.provider_type,
                provider_account_id=copy.provider_account_id,
                provider_calendar_id=copy.provider_calendar_id,
                visibility_state=copy.event_visibility_state,
                is_preferred=copy.id == (group.preferred_event_id if group else event.id),
            )
            for copy in copies
        ],
        preferred_reason=_describe_preference(copies, event),
        latest_sync=latest_sync,
    )
```

Keep `_describe_preference(...)` short and operator-facing, for example:

```python
def _describe_preference(copies: list[Event], event: Event) -> str:
    if event.location:
        return "This copy is preferred because it carries the clearest appointment details."
    if event.provider_type == "google":
        return "This copy is preferred because Google copies currently rank highest when details are otherwise equal."
    return "This copy is preferred based on the current duplicate grouping rules."
```

- [ ] **Step 4: Create the route and template**

Create `src/calsync/web/routes/events.py`:

```python
router = APIRouter(prefix="/admin/events")


@router.get("/{event_id}")
def event_explain_page(
    event_id: str,
    request: Request,
    session: Session = Depends(get_db),
    templates: Jinja2Templates = Depends(get_templates),
    current_admin: AdminUser = Depends(require_admin),
):
    try:
        explain_view = build_event_explain_view(session, event_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request,
        "event_explain.html",
        {
            "current_admin": current_admin,
            "event_view": explain_view,
        },
    )
```

Register it in `src/calsync/web/routes/__init__.py`:

```python
from .events import router as events_router
...
router.include_router(events_router)
```

Create `src/calsync/web/templates/event_explain.html` with sections:

```html
<article class="panel">
  <h2>Why CalSync is showing this appointment</h2>
  <p>{{ event_view.preferred_reason }}</p>
</article>

<article class="panel">
  <h2>Grouped source copies</h2>
  <ul class="review-event-list">
    {% for copy in event_view.copies %}
    <li class="review-event-card">
      <div class="review-event-main">
        <strong>{{ copy.title }}</strong>
        <span class="subtle">{{ copy.provider_type }} · {{ copy.provider_account_id }} · {{ copy.provider_calendar_id }}</span>
        <span class="subtle">Visibility: {{ copy.visibility_state }}</span>
      </div>
      {% if copy.is_preferred %}
      <span class="review-chip review-chip--preferred">Preferred copy</span>
      {% endif %}
    </li>
    {% endfor %}
  </ul>
</article>
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```bash
pytest tests/test_event_explain_page.py -v
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add src/calsync/services/event_explain.py src/calsync/web/routes/events.py src/calsync/web/routes/__init__.py src/calsync/web/templates/event_explain.html tests/test_event_explain_page.py
git commit -m "feat: add event explain view"
```

---

### Task 4: Connect Inbox Actions To The Explain Page And Refresh Docs

**Files:**
- Modify: `src/calsync/services/problems.py`
- Modify: `src/calsync/web/templates/problems.html`
- Modify: `README.md`
- Modify: `docs/ops.md`
- Modify: `docs/prompts/backend.md`
- Test: `tests/test_problem_pages.py`
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write the failing docs and inbox-link tests**

```python
def test_problem_page_links_duplicate_items_to_event_explain_view(tmp_path: Path) -> None:
    with _build_client(tmp_path) as client:
        _login(client)
        response = client.get("/admin/problems")

    assert response.status_code == 200
    assert "/admin/events/" in response.text
    assert "Explain this event" in response.text
```

```python
def test_docs_cover_event_explain_and_richer_problem_actions() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "/admin/events/" in readme_content
    assert "explain this event" in ops_content
    assert "#15" in prompt_content
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
pytest tests/test_problem_pages.py -k "links_duplicate_items_to_event_explain_view" tests/test_docs.py -k "event_explain_and_richer_problem_actions" -v
```

Expected:

- FAIL until the inbox links and docs are updated

- [ ] **Step 3: Connect problem actions to explain links and update docs**

Ensure duplicate problems expose explain links from the problem service:

```python
ProblemAction(
    label="Explain this event",
    target=f"/admin/events/{duplicate_group.group.preferred_event_id}",
)
```

Document in:

- `README.md`
- `docs/ops.md`
- `docs/prompts/backend.md`

Use wording like:

```md
- `/admin/events/{event_id}` explains why one copy is visible, hidden, or preferred
- `/admin/problems` now offers provider-aware duplicate actions plus `Explain this event`
```

- [ ] **Step 4: Run focused regression checks**

Run:

```bash
pytest tests/test_problem_pages.py tests/test_event_explain_page.py tests/test_docs.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/problems.py src/calsync/web/templates/problems.html README.md docs/ops.md docs/prompts/backend.md tests/test_problem_pages.py tests/test_docs.py
git commit -m "docs: capture problem inbox explain workflow"
```

---

### Task 5: Final Verification, Tracking, And Deployment

**Files:**
- Modify: `README.md` (only if verification reveals doc drift)
- Modify: `docs/ops.md` (only if verification reveals doc drift)
- Modify: `docs/prompts/backend.md` (only if verification reveals doc drift)

- [ ] **Step 1: Run the full automated suite**

Run:

```bash
pytest -v
```

Expected:

- PASS for the full suite

- [ ] **Step 2: Verify Docker Compose rendering**

Run:

```bash
docker compose config
```

Expected:

- clean rendered config with no validation errors

- [ ] **Step 3: Push the completed branch state**

Run:

```bash
git push origin HEAD:main
```

Expected:

- remote `main` advances to the new feature commit

- [ ] **Step 4: Redeploy to the Pi**

Run:

```bash
plink -batch -ssh kay@192.168.50.232 -pw kay "set -e; cd ~/apps/calsync; git fetch origin; git checkout main; git reset --hard origin/main; docker compose up --build -d"
```

Expected:

- Pi checkout fast-forwards to the new commit and the stack rebuilds cleanly

- [ ] **Step 5: Verify live health and private-route gating**

Run:

```bash
plink -batch -ssh kay@192.168.50.232 -pw kay "cd ~/apps/calsync; docker compose ps; curl -fsS http://127.0.0.1:3080/healthz; echo; curl -fsS https://calsync.neonbutterfly.net/healthz; echo; curl -s -o /dev/null -w '%{http_code}\n' https://calsync.neonbutterfly.net/login; curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://calsync.neonbutterfly.net/admin/events/example-id"
```

Expected:

- Pi web container healthy
- local and public health endpoints return `{"status":"ok"}`
- login returns `200`
- private event routes redirect to `/login` when unauthenticated

- [ ] **Step 6: Update and close GitHub issue**

Run:

```bash
gh issue comment 15 --body "Implemented on <commit> with test evidence, compose validation, and Pi deployment checks."
gh issue close 15 --comment "Verified and shipped."
```

Expected:

- issue `#15` contains evidence and is closed only after verification is complete

---

## Self-Review

### Spec coverage

- richer `/admin/problems` actions: covered by Tasks 1, 2, and 4
- per-event explain page: covered by Tasks 3 and 4
- reuse of existing trust state: covered by Tasks 1 and 3
- docs and operator workflow updates: covered by Task 4
- validation and live deployment: covered by Task 5

### Placeholder scan

- no `TBD`, `TODO`, or vague “handle later” wording left in the tasks
- each code-changing task includes concrete snippets, commands, and expected outcomes

### Type consistency

- duplicate problem actions consistently use `ProblemAction`
- explain flow consistently uses `/admin/events/{event_id}`
- existing reconciliation primitives remain `prefer_event_in_group`, `restore_hidden_duplicate`, and `list_group_events`
