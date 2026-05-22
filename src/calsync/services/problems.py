from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from calsync.models import ProviderAccount, SyncLog
from calsync.services.reconciliation import collect_trust_metrics, list_duplicate_groups


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


def list_operator_problems(session: Session) -> list[ProblemItem]:
    problems: list[ProblemItem] = []

    duplicate_groups = list_duplicate_groups(session)
    for duplicate_group in duplicate_groups:
        preferred_event = next(
            (event for event in duplicate_group.events if event.id == duplicate_group.group.preferred_event_id),
            duplicate_group.events[0],
        )
        problems.append(
            ProblemItem(
                id=f"duplicate-{duplicate_group.group.id}",
                category="duplicate",
                severity="medium",
                title="Possible duplicate appointment",
                summary=(
                    f"{duplicate_group.group.display_title} looks like the same appointment in "
                    f"{len(duplicate_group.events)} synced copies."
                ),
                source_label=f"{preferred_event.provider_type} · {preferred_event.provider_account_id}",
                primary_action=ProblemAction(
                    label="Review duplicates",
                    target=f"/admin/review#group-{duplicate_group.group.id}",
                ),
            )
        )

    accounts = session.scalars(
        select(ProviderAccount)
        .options(selectinload(ProviderAccount.sync_logs))
        .order_by(ProviderAccount.display_name, ProviderAccount.provider_account_id)
    ).all()

    for account in accounts:
        problems.extend(_account_problems(session, account))

    return sorted(problems, key=_problem_sort_key)


def count_operator_problems(session: Session) -> int:
    return len(list_operator_problems(session))


def build_problem_summary(session: Session) -> dict[str, int]:
    trust_metrics = collect_trust_metrics(session)
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
