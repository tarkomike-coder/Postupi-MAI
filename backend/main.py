from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="Postupi MAI API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    if __name__ != "__main__":
        app.mount("/", StaticFiles(directory="site", html=True), name="site")

    return app


app = create_app()
