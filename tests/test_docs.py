from __future__ import annotations

from pathlib import Path


def test_readme_mentions_required_operator_topics() -> None:
    content = Path("README.md").read_text(encoding="utf-8").lower()

    required_phrases = [
        "project overview",
        "first-run admin setup",
        "mfa",
        "totp",
        "recovery codes",
        "reset-admin-password",
        "reset-admin-mfa",
        "google oauth setup",
        "apple app-specific password",
        "docker deployment",
        "app_host=0.0.0.0",
        "app_port=3080",
        "public_base_url",
        "lan",
        "backup",
        "restore",
        "known limitations",
    ]

    for phrase in required_phrases:
        assert phrase in content


def test_ops_and_prompt_docs_capture_phase1_scope() -> None:
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()

    assert "backup" in ops_content
    assert "restore" in ops_content
    assert "docker compose up --build" in ops_content
    assert "reset-admin-password" in ops_content
    assert "reset-admin-mfa" in ops_content
    assert "one google oauth web client is enough for multiple connected google accounts" in ops_content
    assert "test users" in ops_content

    assert "one google cloud project and one oauth web client" in readme_content
    assert "each google account still has to go through its own consent flow" in readme_content
    assert "external" in readme_content
    assert "internal" in readme_content

    assert "#1" in prompt_content
    assert "mandatory mfa" in prompt_content
    assert "read-only" in prompt_content
    assert "mock provider" in prompt_content


def test_docs_cover_public_app_url_and_private_flightboard() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8")
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8")
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8")

    assert "Public App URL" in readme_content
    assert "https://calsync.neonbutterfly.net" in readme_content
    assert "Flightboard" in readme_content

    assert "Public App URL" in ops_content
    assert "https://calsync.neonbutterfly.net" in ops_content
    assert "Connect Google Account" in ops_content
    assert "/admin/flightboard" in ops_content
    assert "Flightboard" in ops_content

    assert "#4" in prompt_content
    assert "https://calsync.neonbutterfly.net" in prompt_content
    assert "flightboard" in prompt_content.lower()


def test_docs_cover_flightboard_current_upcoming_ranges() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "current and upcoming" in readme_content
    assert "day" in readme_content and "week" in readme_content and "month" in readme_content
    assert "never shows events that have already ended" in readme_content

    assert "current and upcoming enabled calendar events" in ops_content
    assert "day" in ops_content and "week" in ops_content and "month" in ops_content
    assert "excludes events whose end time has already passed" in ops_content

    assert "#5" in prompt_content
    assert "current and upcoming" in prompt_content
    assert "day" in prompt_content and "week" in prompt_content and "month" in prompt_content


def test_docs_cover_trust_review_and_duplicate_cleanup() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "/admin/review" in readme_content
    assert "deleted_upstream" in readme_content
    assert "duplicate grouping" in readme_content
    assert "same appointment twice" in readme_content

    assert "/admin/review" in ops_content
    assert "possible duplicates" in ops_content
    assert "keep this copy" in ops_content
    assert "deleted_upstream" in ops_content

    assert "#11" in prompt_content
    assert "#12" in prompt_content
    assert "/admin/review" in prompt_content
    assert "hidden duplicate" in prompt_content


def test_docs_cover_problem_to_fix_inbox() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "/admin/problems" in readme_content
    assert "problem-to-fix inbox" in readme_content

    assert "/admin/problems" in ops_content
    assert "problem to fix list" in ops_content
    assert "problems to fix" in ops_content
    assert "sync now" in ops_content

    assert "#14" in prompt_content
    assert "/admin/problems" in prompt_content
    assert "problem-to-fix inbox" in prompt_content


def test_docs_cover_event_explain_and_richer_problem_actions() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "/admin/events/" in readme_content
    assert "explain this event" in readme_content

    assert "/admin/events/" in ops_content
    assert "explain this event" in ops_content
    assert "keep google copy" in ops_content

    assert "#15" in prompt_content
    assert "/admin/events/" in prompt_content
    assert "explain this event" in prompt_content


def test_docs_cover_ranked_utility_roadmap() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "product roadmap" in readme_content
    assert "source confidence" in readme_content
    assert "connector sdk" in readme_content
    assert "saved views" in readme_content

    assert "#16" in prompt_content
    assert "source confidence" in prompt_content
    assert "connector sdk" in prompt_content


def test_docs_cover_write_capable_foundation_slice() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "connections" in readme_content
    assert "write-capable scheduling" in readme_content
    assert "apple connector" in readme_content
    assert "app-specific password" in readme_content
    assert "check availability" in readme_content
    assert "writable booking target" in readme_content
    assert "writable provider" in readme_content
    assert "microsoft" in readme_content
    assert "does not yet ship a real microsoft oauth connect flow" in readme_content
    assert "scheduling workspace" in readme_content

    assert "connections" in ops_content
    assert "receive new bookings" in ops_content
    assert "writable booking target" in ops_content
    assert "writable provider" in ops_content
    assert "microsoft sign-in and calendar permissions" in ops_content
    assert "full booking pages are not shipped in this slice" in ops_content

    assert "#17" in prompt_content
    assert "write-capable scheduling product" in prompt_content
    assert "apple connector data" in prompt_content
    assert "calendar roles" in prompt_content
    assert "no full booking pages in this slice" in prompt_content
