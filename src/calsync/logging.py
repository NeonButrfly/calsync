import logging

from calsync.config import Settings, build_healthcheck_url


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def log_startup(logger: logging.Logger, settings: Settings) -> None:
    logger.info(
        "Starting CalSync on %s:%s",
        settings.bind_host,
        settings.bind_port,
    )
    if settings.public_base_url:
        logger.info("Configured public base URL: %s", str(settings.public_base_url))
    logger.info("Healthcheck URL: %s", build_healthcheck_url(settings))
