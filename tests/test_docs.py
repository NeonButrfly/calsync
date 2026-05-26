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


def test_docs_cover_trust_ux_and_auth_refresh() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "continue with google" in readme_content
    assert "continue with facebook" in readme_content
    assert "calsync currently recommends keeping" in readme_content
    assert "why a pair of events was grouped" in readme_content

    assert "/login" in ops_content
    assert "welcome back" in ops_content
    assert "continue with microsoft" in ops_content
    assert "fix what needs attention" in ops_content
    assert "which copy calsync currently recommends keeping" in ops_content

    assert "#24" in prompt_content
    assert "#25" in prompt_content
    assert "social sign-in options" in prompt_content
    assert "preferred-copy guidance" in prompt_content


def test_docs_cover_sidebar_availability_help_and_trust_attention_window() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "persistent left sidebar" in readme_content
    assert "inline helper copy and select tooltips" in readme_content
    assert "ignore stale lookback noise" in readme_content
    assert "exact connected copy" in readme_content

    assert "persistent left sidebar" in ops_content
    assert "select tooltips" in ops_content
    assert "active inbox ignores old lookback noise" in ops_content

    assert "#26" in prompt_content
    assert "tooltip" in prompt_content
    assert "sidebar" in prompt_content
    assert "exact connected calendar copy" in prompt_content


def test_docs_cover_cache_busting_and_non_current_year_dates() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "asset-version query string" in readme_content
    assert "outside the current year" in readme_content

    assert "cache-busted `app.css?v=...` url" in ops_content
    assert "trust-facing dates show the year" in ops_content

    assert "#27" in prompt_content
    assert "stylesheet cache busting" in prompt_content
    assert "upcoming schedule" in prompt_content


def test_docs_cover_break_glass_admin_login() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "ensure-break-glass-admin" in readme_content
    assert "mfa-exempt" in readme_content
    assert "standard admin accounts remain password plus mfa" in readme_content

    assert "ensure-break-glass-admin" in ops_content
    assert "mfa-exempt after the password step" in ops_content
    assert "rendered browser verification" in ops_content

    assert "#28" in prompt_content
    assert "mfa bypass" in prompt_content
    assert "break-glass account" in prompt_content


def test_docs_cover_scrollable_sidebar_and_trust_source_specificity() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "sidebar navigation now scrolls independently" in readme_content
    assert "purpose guide" in readme_content
    assert "trust inbox and review timestamps now always show the year" in readme_content

    assert "sidebar navigation scrolls independently" in ops_content
    assert "purpose guide" in ops_content
    assert "exact provider, account, and calendar copy" in ops_content

    assert "#29" in prompt_content
    assert "question-mark tooltip hints" in prompt_content
    assert "year-explicit timestamps" in prompt_content


def test_docs_cover_collapsible_calendar_workspace_and_event_explain_disclosures() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "collapsible section" in readme_content
    assert "show source details" in readme_content
    assert "current recommendation" in readme_content

    assert "collapsible section" in ops_content
    assert "show source details" in ops_content
    assert "current recommendation" in ops_content

    assert "#30" in prompt_content
    assert "show source details" in prompt_content
    assert "current recommendation" in prompt_content


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
    assert "outlook / microsoft 365 account connection through browser-based oauth" in readme_content
    assert "microsoft calendar discovery" in readme_content
    assert "microsoft read-only event sync" in readme_content
    assert "shared microsoft oauth app settings" in readme_content
    assert "broader provider write-back and booking-page behavior remain follow-on work under issue `#23`" in readme_content
    assert "scheduling workspace" in readme_content

    assert "connections" in ops_content
    assert "receive new bookings" in ops_content
    assert "writable booking target" in ops_content
    assert "writable provider" in ops_content
    assert "connect microsoft account" in ops_content
    assert "microsoft calendar discovery is live" in ops_content
    assert "microsoft sync is read-only in this slice" in ops_content
    assert "microsoft oauth app" in ops_content
    assert "active callback url" in ops_content
    assert "full booking pages are not shipped in this slice" in ops_content

    assert "#17" in prompt_content
    assert "#21" in prompt_content
    assert "#22" in prompt_content
    assert "#23" in prompt_content
    assert "write-capable scheduling product" in prompt_content
    assert "apple connector data" in prompt_content
    assert "calendar roles" in prompt_content
    assert "no booking pages or public scheduling surfaces are introduced here" in prompt_content
    assert "microsoft oauth app" in prompt_content
    assert "microsoft account connection, calendar discovery, and sync are now live in this slice" in prompt_content


def test_docs_cover_first_writable_appointment_editor() -> None:
    readme_content = Path("README.md").read_text(encoding="utf-8").lower()
    ops_content = Path("docs/ops.md").read_text(encoding="utf-8").lower()
    prompt_content = Path("docs/prompts/backend.md").read_text(encoding="utf-8").lower()

    assert "/admin/appointments/new" in readme_content
    assert "write back to writable google calendars" in readme_content
    assert "write back to writable apple/icloud calendars" in readme_content
    assert "edit appointment" in readme_content
    assert "cancel appointment" in readme_content
    assert "clears the old incremental google sync tokens" in readme_content

    assert "/admin/appointments/new" in ops_content
    assert "writable appointment editor" in ops_content
    assert "microsoft stays read-only in this slice" in ops_content
    assert "receive new bookings" in ops_content
    assert "clears stale google incremental sync tokens" in ops_content

    assert "#31" in prompt_content
    assert "first writable appointment editor" in prompt_content
    assert "google and apple/icloud" in prompt_content
    assert "stale google incremental sync tokens" in prompt_content
