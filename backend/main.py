from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    init_db()
    yield


def create_app(*, mount_static: bool = True) -> FastAPI:
    app = FastAPI(title="Postupi MAI API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    if mount_static:
        app.mount("/", StaticFiles(directory="site", html=True), name="site")

    return app


app = create_app()
