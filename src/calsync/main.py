from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from calsync.config import get_settings
from calsync.logging import get_logger, log_startup


def create_app(settings=None) -> FastAPI:
    resolved_settings = settings or get_settings()
    logger = get_logger("calsync.startup")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log_startup(logger, resolved_settings)
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.settings = resolved_settings

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
