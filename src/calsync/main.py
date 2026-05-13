from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from calsync.config import get_settings
from calsync.logging import get_logger, log_startup
from calsync.web import router as web_router
from calsync.web.deps import SignedCookieSessionMiddleware, get_session_secret


def create_app(settings=None) -> FastAPI:
    resolved_settings = settings or get_settings()
    logger = get_logger("calsync.startup")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log_startup(logger, resolved_settings)
        yield

    app = FastAPI(lifespan=lifespan)
    app.state.settings = resolved_settings
    app.add_middleware(
        SignedCookieSessionMiddleware,
        secret_key=get_session_secret(resolved_settings),
    )
    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(web_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def home() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
