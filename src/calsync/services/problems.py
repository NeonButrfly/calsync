from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from calsync.models import ProviderAccount, ProviderCalendar, SyncLog
from calsync.services.reconciliation import (
    DuplicateGroupView,
    collect_trust_metrics,
    is_event_attention_relevant,
    list_duplicate_groups,
)


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
    extra_actions: list[ProblemAction] = field(default_factory=list)
    event_id: str | None = None
    preferred_label: str | None = None
    context_lines: list[str] = field(default_factory=list)


def list_operator_problems(session: Session) -> list[ProblemItem]:
    problems: list[ProblemItem] = []

    duplicate_groups = list_duplicate_groups(session, attention_only=True)
    for duplicate_group in duplicate_groups:
        preferred_event = next(
            (event for event in duplicate_group.events if event.id == duplicate_group.group.preferred_event_id),
            duplicate_group.events[0],
        )
        problems.append(
            ProblemItem(
                id=duplicate_group.anchor_id,
                category="duplicate",
                severity="medium",
                title=f"Possible duplicate appointment: {duplicate_group.group.display_title}",
                summary=(
                    f"{duplicate_group.group.display_title} appears in {len(duplicate_group.events)} "
                    f"calendar copies around the same time."
                ),
                source_label=_build_duplicate_source_label(session, duplicate_group),
                primary_action=ProblemAction(
                    label="Resolve duplicate",
                    target=f"/admin/review#{duplicate_group.anchor_id}",
                ),
                extra_actions=_duplicate_problem_actions(session, duplicate_group),
                event_id=duplicate_group.group.preferred_event_id,
                preferred_label=_build_duplicate_preferred_label(session, preferred_event),
                context_lines=_build_duplicate_context_lines(session, duplicate_group),
            )
        )

    accounts = session.scalars(
        select(ProviderAccount)
        .order_by(ProviderAccount.display_name, ProviderAccount.provider_account_id)
    ).all()

    for account in accounts:
        problems.extend(_account_problems(session, account))

    return sorted(problems, key=_problem_sort_key)


def count_operator_problems(session: Session) -> int:
    return len(list_operator_problems(session))


def build_problem_summary(session: Session) -> dict[str, int]:
    trust_metrics = collect_trust_metrics(session, attention_only=True)
    problems = list_operator_problems(session)
    return {
        "problem_count": len(problems),
        "duplicate_count": trust_metrics["duplicate_groups"],
        "sync_problem_count": len(
            [problem for problem in problems if problem.category in {"sync", "auth"}]
        ),
    }


def _account_problems(session: Session, account: ProviderAccount) -> list[ProblemItem]:
    metadata = dict(account.provider_metadata or {})
    account_name = account.display_name or account.provider_account_id
    source_label = f"{account.provider_type} · {account_name}"
    problems: list[ProblemItem] = []

    google_reconnect_required = bool(metadata.get("google_reconnect_required"))
    google_auth_status = str(metadata.get("google_auth_status") or "")
    account_auth_status = str(metadata.get("auth_status") or "")
    last_auth_error = metadata.get("google_last_auth_error") or metadata.get("last_auth_error")

    if google_reconnect_required or google_auth_status == "reconnect_required":
        problems.append(
            ProblemItem(
                id=f"auth-{account.id}",
                category="auth",
                severity="high",
                title="Google account needs reconnection",
                summary=str(last_auth_error or "Google access needs to be reconnected before syncing can continue."),
                source_label=source_label,
                primary_action=ProblemAction(
                    label="Reconnect in accounts",
                    target="/admin/accounts",
                ),
            )
        )
        return problems

    if account_auth_status == "error":
        problems.append(
            ProblemItem(
                id=f"auth-{account.id}",
                category="auth",
                severity="high",
                title="Account authentication failed",
                summary=str(last_auth_error or "Provider authentication failed."),
                source_label=source_label,
                primary_action=ProblemAction(
                    label="Open accounts",
                    target="/admin/accounts",
                ),
            )
        )
        return problems

    latest_log = session.scalar(
        select(SyncLog)
        .where(SyncLog.provider_account_pk == account.id)
        .order_by(SyncLog.started_at.desc(), SyncLog.id.desc())
    )

    if latest_log is None:
        problems.append(
            ProblemItem(
                id=f"sync-{account.id}-first-run",
                category="sync",
                severity="medium",
                title="Account has never synced",
                summary="Run the first sync so CalSync can discover calendars and pull events.",
                source_label=source_label,
                primary_action=ProblemAction(
                    label="Run first sync",
                    target=f"/admin/problems/actions/sync/{account.id}",
                    method="post",
                ),
                secondary_action=ProblemAction(
                    label="Open sync status",
                    target="/admin/sync",
                ),
            )
        )
        return problems

    if latest_log.status != "success" or bool(latest_log.error_text):
        problems.append(
            ProblemItem(
                id=f"sync-{account.id}-error",
                category="sync",
                severity="high",
                title="Latest sync needs attention",
                summary=str(latest_log.error_text or f"Last sync finished with status {latest_log.status}."),
                source_label=source_label,
                primary_action=ProblemAction(
                    label="Sync now",
                    target=f"/admin/problems/actions/sync/{account.id}",
                    method="post",
                ),
                secondary_action=ProblemAction(
                    label="Open sync status",
                    target="/admin/sync",
                ),
            )
        )

    return problems


def _problem_sort_key(problem: ProblemItem) -> tuple[int, str, str]:
    severity_rank = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }.get(problem.severity, 3)
    return (severity_rank, problem.category, problem.title)


def _duplicate_problem_actions(
    session: Session,
    duplicate_group: DuplicateGroupView,
) -> list[ProblemAction]:
    actions: list[ProblemAction] = []

    for event in duplicate_group.events:
        if event.id == duplicate_group.group.preferred_event_id:
            continue
        actions.append(
            ProblemAction(
                label=f"Keep {_format_event_copy_label(session, event)}",
                target=f"/admin/problems/actions/event/{event.id}/prefer",
                method="post",
            )
        )

    hidden_duplicates = [
        event for event in duplicate_group.events if event.event_visibility_state == "hidden_duplicate"
    ]
    if hidden_duplicates:
        actions.append(
            ProblemAction(
                label="Show both" if len(duplicate_group.events) == 2 else "Show all copies",
                target=f"/admin/problems/actions/event/{duplicate_group.group.preferred_event_id}/show-both",
                method="post",
            )
        )

    actions.append(
        ProblemAction(
            label="Explain this event",
            target=f"/admin/events/{duplicate_group.group.preferred_event_id}",
        )
    )
    return actions


def _build_duplicate_preferred_label(session: Session, preferred_event) -> str:
    provider_name = _friendly_provider_name(preferred_event.provider_type)
    return (
        f"CalSync recommends keeping the {provider_name} copy from "
        f"{_account_label(session, preferred_event)} · {_calendar_label(session, preferred_event)}."
    )


def _build_duplicate_context_lines(
    session: Session,
    duplicate_group: DuplicateGroupView,
) -> list[str]:
    providers = []
    for event in duplicate_group.events:
        providers.append(_format_event_context_line(session, event))
    return providers


def _build_duplicate_source_label(
    session: Session,
    duplicate_group: DuplicateGroupView,
) -> str:
    preferred_event = next(
        (event for event in duplicate_group.events if event.id == duplicate_group.group.preferred_event_id),
        duplicate_group.events[0],
    )
    starts_at = preferred_event.starts_at
    when = f"{starts_at.strftime('%a %b')} {starts_at.day} at {starts_at.strftime('%I:%M %p').lstrip('0')} UTC"
    return f"{when} · {_account_label(session, preferred_event)}"


def _format_event_copy_label(session: Session, event) -> str:
    provider_name = _friendly_provider_name(event.provider_type)
    calendar_label = _calendar_label(session, event)
    return f"{provider_name} copy from {calendar_label}"


def _format_event_context_line(session: Session, event) -> str:
    provider_name = _friendly_provider_name(event.provider_type)
    account_label = _account_label(session, event)
    calendar_label = _calendar_label(session, event)
    return f"{provider_name}: {account_label} - {calendar_label}"


def _friendly_provider_name(provider_type: str) -> str:
    return {
        "google": "Google",
        "icloud_caldav": "Apple",
        "microsoft": "Microsoft",
        "mock": "Mock",
    }.get(provider_type, provider_type.replace("_", " ").title())


def _account_label(session: Session, event) -> str:
    if event.provider_account_pk:
        account = session.get(ProviderAccount, event.provider_account_pk)
        if account is not None and account.display_name:
            return account.display_name
    return event.provider_account_id


def _calendar_label(session: Session, event) -> str:
    if event.provider_calendar_pk:
        calendar = session.get(ProviderCalendar, event.provider_calendar_pk)
        if calendar is not None and calendar.name:
            return calendar.name
    return event.provider_calendar_id
