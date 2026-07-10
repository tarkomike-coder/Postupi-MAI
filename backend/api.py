from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import SessionLocal
from .services.search import SearchRateLimited, build_search_response, latest_status

router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    application_id: str = Field(min_length=1, max_length=40)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def normalize_application_id(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("select 1"))
    status = latest_status(db)
    return {"status": "ok" if status.get("has_data") else "no_data", **status}


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    return latest_status(db)


@router.post("/search")
def search(payload: SearchRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        return build_search_response(
            db,
            application_id=normalize_application_id(payload.application_id),
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except SearchRateLimited as exc:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "retry_after_seconds": exc.retry_after_seconds,
                "message": "Слишком много запросов подряд. Поиск временно ограничен, попробуйте позже.",
            },
        )
