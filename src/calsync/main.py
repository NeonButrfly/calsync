from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from calsync.api.routes.appointments import router as appointments_router
from calsync.api.routes.health import router as health_router
from calsync.api.routes.readiness import router as readiness_router
from calsync.web.routes.console import router as console_router
from pathlib import Path


def create_app() -> FastAPI:
    app = FastAPI(title="CalSync", version="0.2.0", docs_url=None, redoc_url=None)
    app.include_router(appointments_router)
    app.include_router(health_router)
    app.include_router(readiness_router)
    app.include_router(console_router)
    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/info")
    def api_info() -> dict[str, str]:
        return {"service": "calsync", "mode": "apple-first"}

    return app


app = create_app()
