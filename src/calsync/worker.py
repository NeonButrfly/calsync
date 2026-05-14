from __future__ import annotations

from time import sleep

from sqlalchemy import select

from calsync.config import Settings, get_settings
from calsync.db import create_session_factory
from calsync.logging import get_logger
from calsync.models import ProviderAccount
from calsync.services.sync import sync_account


logger = get_logger("calsync.worker")


def run_sync_cycle(settings: Settings | None = None) -> int:
    resolved_settings = settings or get_settings()
    session_factory = create_session_factory(resolved_settings)

    with session_factory() as session:
        account_ids = list(
            session.scalars(
                select(ProviderAccount.id).order_by(ProviderAccount.provider_type, ProviderAccount.id)
            )
        )

    synced_accounts = 0
    for account_id in account_ids:
        with session_factory() as session:
            try:
                sync_account(
                    session,
                    account_id,
                    trigger="scheduled",
                    settings=resolved_settings,
                )
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("Worker sync failed for account %s", account_id)
            else:
                synced_accounts += 1

    return synced_accounts


def main() -> None:
    settings = get_settings()
    logger.info(
        "Starting CalSync worker with poll interval %s seconds",
        settings.sync_poll_seconds,
    )
    while True:
        synced_accounts = run_sync_cycle(settings)
        logger.info("Worker cycle complete. Accounts synced: %s", synced_accounts)
        sleep(settings.sync_poll_seconds)


if __name__ == "__main__":
    main()
