from fastapi import FastAPI

from calsync.api.routes.appointments import router as appointments_router
from calsync.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="CalSync", version="0.2.0", docs_url=None, redoc_url=None)
    app.include_router(appointments_router)
    app.include_router(health_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "calsync", "mode": "apple-first"}

    return app


app = create_app()
