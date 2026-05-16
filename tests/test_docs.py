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
