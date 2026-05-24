# CalSync Source Confidence And Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sticky source-confidence policies and clearer event lineage so CalSync can explain and remember why one duplicate copy wins over another.

**Architecture:** Extend the existing reconciliation and event explain workflow with a small policy layer instead of replacing the current duplicate engine. Keep all provider behavior read-only, store operator preference overrides durably, and surface confidence reasons through the problem inbox, review page, dashboard summaries, and event explain page.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Jinja templates, PostgreSQL/SQLite test compatibility, pytest

---

## File Structure

### Existing files to modify

- `src/calsync/models/events.py`
  - attach provider-preference and confidence metadata needed by explain views
- `src/calsync/services/reconciliation.py`
  - apply confidence scoring and sticky preference overrides when selecting the preferred copy
- `src/calsync/services/problems.py`
  - surface policy-applied versus still-ambiguous duplicate problems
- `src/calsync/services/event_explain.py`
  - show the winning reason, losing reason, and sticky override state
- `src/calsync/web/routes/problems.py`
  - add sticky keep actions such as `Always prefer Google here`
- `src/calsync/web/routes/events.py`
  - expose sticky override actions and richer lineage details
- `src/calsync/web/routes/review.py`
  - reflect policy-applied state in duplicate cleanup
- `src/calsync/web/routes/dashboard.py`
  - show source-confidence counts in the trust summary
- `src/calsync/web/templates/problems.html`
  - show clearer action text and confidence badges
- `src/calsync/web/templates/event_explain.html`
  - render confidence reasons and sticky policy state
- `src/calsync/web/templates/review.html`
  - show policy-applied duplicate groups separately from unresolved groups
- `src/calsync/web/templates/dashboard.html`
  - show a summary such as `policy-applied duplicates`
- `README.md`
  - document sticky source-confidence behavior
- `docs/ops.md`
  - document the operator workflow for sticky duplicate preferences
- `docs/prompts/backend.md`
  - capture the shipped behavior for the new issue

### New files to create

- `alembic/versions/20260524_01_source_confidence_policies.py`
  - schema migration for sticky duplicate preference overrides
- `src/calsync/models/trust.py`
  - policy model for duplicate preference overrides
- `tests/test_source_confidence.py`
  - reconciliation and sticky override coverage
- `tests/test_problem_policy_actions.py`
  - duplicate action and redirect coverage
- `tests/test_event_explain_page.py`
  - extend coverage for confidence reasons and sticky state

### Boundaries to preserve

- no provider write-back
- no raw source event deletion
- no fuzzy machine-learning matcher in this slice
- no new non-calendar connector yet

---

### Task 1: Add Sticky Duplicate Preference Schema

**Files:**
- Create: `alembic/versions/20260524_01_source_confidence_policies.py`
- Create: `src/calsync/models/trust.py`
- Modify: `src/calsync/models/__init__.py`
- Test: `tests/test_source_confidence.py`

- [ ] **Step 1: Write the failing schema test**

```python
def test_duplicate_preference_override_round_trips(migrated_session_factory):
    from calsync.models.trust import DuplicatePreferenceOverride

    with migrated_session_factory() as session:
        override = DuplicatePreferenceOverride(
            scope_type="group",
            scope_key="duplicate-group-1",
            preferred_provider="google",
            reason="operator_preference",
        )
        session.add(override)
        session.commit()
        override_id = override.id

    with migrated_session_factory() as session:
        reloaded = session.get(DuplicatePreferenceOverride, override_id)
        assert reloaded is not None
        assert reloaded.scope_type == "group"
        assert reloaded.preferred_provider == "google"
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_source_confidence.py::test_duplicate_preference_override_round_trips -v`
Expected: FAIL because the trust model and migration do not exist yet.

- [ ] **Step 3: Add the model and migration**

```python
class DuplicatePreferenceOverride(Base):
    __tablename__ = "duplicate_preference_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    preferred_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False, default="operator_preference")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False, default=utcnow)
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_source_confidence.py::test_duplicate_preference_override_round_trips tests/test_event_reconciliation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add alembic src/calsync/models tests/test_source_confidence.py
git commit -m "feat: add source confidence policy schema"
```

### Task 2: Teach Reconciliation To Respect Sticky Provider Preference

**Files:**
- Modify: `src/calsync/services/reconciliation.py`
- Modify: `src/calsync/models/events.py`
- Test: `tests/test_source_confidence.py`

- [ ] **Step 1: Write the failing reconciliation tests**

```python
def test_group_preference_override_prefers_google_copy(session):
    google_event, icloud_event = make_duplicate_pair(session)
    set_group_preference_override(
        session,
        scope_key=duplicate_group_anchor_id([google_event, icloud_event]),
        preferred_provider="google",
    )

    groups = rebuild_duplicate_groups(session)

    assert groups[0].preferred_event_id == google_event.id
    assert groups[0].preferred_reason == "sticky_provider_override"
```

```python
def test_without_override_reconciliation_still_uses_default_preference(session):
    google_event, icloud_event = make_duplicate_pair(session)

    groups = rebuild_duplicate_groups(session)

    assert groups[0].preferred_reason in {"default_provider_priority", "confidence_score"}
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_source_confidence.py -k "override_prefers_google_copy or default_preference" -v`
Expected: FAIL because duplicate grouping does not expose policy-aware preference reasons yet.

- [ ] **Step 3: Implement policy-aware preference**

```python
def choose_preferred_event(
    events: Sequence[Event],
    override: DuplicatePreferenceOverride | None,
) -> tuple[Event, str]:
    if override is not None:
        for event in events:
            if event.provider_type == override.preferred_provider:
                return event, "sticky_provider_override"

    ranked = sorted(events, key=build_event_preference_key)
    return ranked[0], ranked[0].preference_reason or "default_provider_priority"
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_source_confidence.py tests/test_event_reconciliation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/reconciliation.py src/calsync/models/events.py tests/test_source_confidence.py
git commit -m "feat: apply sticky source confidence policies"
```

### Task 3: Expose Sticky Actions In Problem Inbox And Event Explain View

**Files:**
- Modify: `src/calsync/services/problems.py`
- Modify: `src/calsync/services/event_explain.py`
- Modify: `src/calsync/web/routes/problems.py`
- Modify: `src/calsync/web/routes/events.py`
- Modify: `src/calsync/web/templates/problems.html`
- Modify: `src/calsync/web/templates/event_explain.html`
- Test: `tests/test_problem_policy_actions.py`
- Test: `tests/test_event_explain_page.py`

- [ ] **Step 1: Write the failing UI action tests**

```python
def test_problem_page_shows_sticky_google_action_for_mixed_provider_duplicate(client, session):
    event_id = seed_google_icloud_duplicate(session)

    response = client.get("/admin/problems", follow_redirects=True)

    assert "Always prefer Google" in response.text
    assert f"/admin/problems/actions/event/{event_id}/prefer/google" in response.text
```

```python
def test_event_explain_page_shows_preferred_reason(client, session):
    event_id = seed_google_icloud_duplicate_with_override(session)

    response = client.get(f"/admin/events/{event_id}", follow_redirects=True)

    assert "sticky provider preference" in response.text.lower()
    assert "Google copy is preferred" in response.text
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_problem_policy_actions.py tests/test_event_explain_page.py -v`
Expected: FAIL because the routes and templates do not expose sticky preference actions or reasons yet.

- [ ] **Step 3: Implement the routes and template wiring**

```python
@router.post("/actions/event/{event_id}/prefer/{provider}")
def prefer_provider_copy(...):
    explain = build_event_explain(...)
    set_group_preference_override(
        session,
        scope_key=explain.group_anchor_id,
        preferred_provider=provider,
    )
    session.commit()
    return RedirectResponse(f"/admin/events/{event_id}", status_code=303)
```

```python
class EventExplainView(TypedDict):
    ...
    preferred_reason: str
    preferred_reason_label: str
    sticky_preference_provider: str | None
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_problem_policy_actions.py tests/test_event_explain_page.py tests/test_problem_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/services/problems.py src/calsync/services/event_explain.py src/calsync/web/routes/problems.py src/calsync/web/routes/events.py src/calsync/web/templates/problems.html src/calsync/web/templates/event_explain.html tests/test_problem_policy_actions.py tests/test_event_explain_page.py
git commit -m "feat: add sticky provider preference actions"
```

### Task 4: Surface Confidence State On Review And Dashboard

**Files:**
- Modify: `src/calsync/web/routes/review.py`
- Modify: `src/calsync/web/routes/dashboard.py`
- Modify: `src/calsync/web/templates/review.html`
- Modify: `src/calsync/web/templates/dashboard.html`
- Test: `tests/test_review_page.py`
- Test: `tests/test_dashboard_pages.py`

- [ ] **Step 1: Write the failing summary tests**

```python
def test_dashboard_shows_policy_applied_duplicate_count(client, session):
    seed_duplicate_with_sticky_preference(session)

    response = client.get("/admin", follow_redirects=True)

    assert "Policy-applied duplicates" in response.text
    assert "1" in response.text
```

```python
def test_review_page_separates_policy_applied_from_needs_attention(client, session):
    seed_duplicate_with_sticky_preference(session)
    seed_unresolved_duplicate(session)

    response = client.get("/admin/review", follow_redirects=True)

    assert "Policy-applied duplicates" in response.text
    assert "Needs attention" in response.text
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_dashboard_pages.py::test_dashboard_shows_policy_applied_duplicate_count tests/test_review_page.py::test_review_page_separates_policy_applied_from_needs_attention -v`
Expected: FAIL because summary views do not split policy-applied and unresolved duplicate groups yet.

- [ ] **Step 3: Implement the summary state**

```python
dashboard["policy_applied_duplicate_count"] = count_policy_applied_groups(session)
dashboard["needs_attention_duplicate_count"] = count_unresolved_duplicate_groups(session)
```

```python
review_groups = {
    "needs_attention": [...],
    "policy_applied": [...],
}
```

- [ ] **Step 4: Run targeted tests**

Run: `pytest tests/test_dashboard_pages.py tests/test_review_page.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/calsync/web/routes/review.py src/calsync/web/routes/dashboard.py src/calsync/web/templates/review.html src/calsync/web/templates/dashboard.html tests/test_review_page.py tests/test_dashboard_pages.py
git commit -m "feat: surface source confidence summaries"
```

### Task 5: Sync Docs And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ops.md`
- Modify: `docs/prompts/backend.md`
- Modify: `tests/test_docs.py`

- [ ] **Step 1: Update operator docs**

Add guidance covering:

- sticky duplicate preference behavior
- source-confidence explanations
- the new operator actions available from `/admin/problems` and `/admin/events/{event_id}`

- [ ] **Step 2: Extend docs tests**

```python
def test_docs_cover_source_confidence_policies() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "sticky provider preference" in readme_content
    assert "always prefer google" in ops_content
    assert "#16" in prompt_content
    assert "source confidence" in prompt_content
```

- [ ] **Step 3: Run validation**

Run: `pytest tests/test_source_confidence.py tests/test_problem_policy_actions.py tests/test_event_explain_page.py tests/test_review_page.py tests/test_dashboard_pages.py tests/test_docs.py -v`
Expected: PASS

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md docs/ops.md docs/prompts/backend.md tests/test_docs.py
git commit -m "docs: capture source confidence roadmap slice"
```
