from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, SearchLog, Snapshot, utcnow


@dataclass(frozen=True)
class SearchRateLimited(Exception):
    retry_after_seconds: int


def _window_start():
    return utcnow() - timedelta(minutes=settings.search_window_minutes)


def _latest_ok_snapshot(db: Session) -> Snapshot | None:
    return (
        db.query(Snapshot)
        .filter(Snapshot.status == "ok")
        .order_by(desc(Snapshot.finished_at), desc(Snapshot.id))
        .first()
    )


def latest_status(db: Session) -> dict:
    snapshot = _latest_ok_snapshot(db)
    if snapshot is None:
        return {"has_data": False, "updated_at": None, "groups_count": 0, "rows_count": 0}
    return {
        "has_data": True,
        "updated_at": snapshot.finished_at or snapshot.started_at,
        "groups_count": snapshot.groups_count,
        "rows_count": snapshot.rows_count,
        "unique_applications_count": snapshot.unique_applications_count,
    }


def _check_rate_limit(db: Session, *, ip: str, application_id: str) -> None:
    since = _window_start()
    logs = (
        db.query(SearchLog)
        .filter(SearchLog.ip == ip, SearchLog.created_at >= since, SearchLog.rate_limited.is_(False))
        .all()
    )
    total = len(logs)
    distinct = {log.application_id for log in logs}
    if total >= settings.search_limit_total or (
        application_id not in distinct and len(distinct) >= settings.search_limit_distinct
    ):
        db.add(
            SearchLog(
                ip=ip,
                user_agent=None,
                application_id=application_id,
                found=False,
                directions_count=0,
                rate_limited=True,
                error_code="rate_limited",
            )
        )
        db.commit()
        raise SearchRateLimited(settings.search_cooldown_minutes * 60)


def _summary_for_directions(directions: list[dict], *, deadline_passed: bool = False) -> str:
    if not directions:
        return "Номер заявления не найден в очных бюджетных конкурсах МАИ."
    if deadline_passed:
        return "Приём документов завершён. Показываем фактическое положение по последним данным."
    if any(item["facts"]["real_gap_to_budget"] == 0 for item in directions):
        return "Есть направления, где заявление сейчас внутри бюджетной зоны по текущим согласиям."
    if any((item["facts"]["real_gap_to_budget"] or 99) <= 5 for item in directions):
        return "Есть направления рядом с бюджетной зоной."
    return "Сейчас все найденные направления вне бюджетной зоны."


def build_search_response(db: Session, *, application_id: str, ip: str, user_agent: str | None) -> dict:
    started = time.perf_counter()
    _check_rate_limit(db, ip=ip, application_id=application_id)
    snapshot = _latest_ok_snapshot(db)
    if snapshot is None:
        log = SearchLog(
            ip=ip,
            user_agent=user_agent,
            application_id=application_id,
            found=False,
            directions_count=0,
            error_code="no_data",
            response_ms=int((time.perf_counter() - started) * 1000),
        )
        db.add(log)
        db.commit()
        return {"found": False, "application_id": application_id, "summary": {"status": "Данные загружаются. Попробуйте позже."}, "directions": []}

    rows = (
        db.query(ApplicantRow, CompetitionGroup, ApplicantDailyMetric)
        .join(CompetitionGroup, CompetitionGroup.id == ApplicantRow.group_id)
        .outerjoin(
            ApplicantDailyMetric,
            (ApplicantDailyMetric.snapshot_id == ApplicantRow.snapshot_id)
            & (ApplicantDailyMetric.group_id == ApplicantRow.group_id)
            & (ApplicantDailyMetric.application_id == ApplicantRow.application_id),
        )
        .filter(ApplicantRow.snapshot_id == snapshot.id, ApplicantRow.application_id == application_id)
        .all()
    )
    directions = []
    for row, group, metric in rows:
        facts = {
            "priority": row.priority,
            "score": row.score,
            "position": metric.position if metric else row.position,
            "consent_position": metric.consent_position if metric else None,
            "real_competitor_position": metric.real_competitor_position if metric else None,
            "above_with_consent": metric.above_with_consent if metric else None,
            "above_without_consent": metric.above_without_consent if metric else None,
            "general_gap_to_budget": metric.general_gap_to_budget if metric else None,
            "consent_gap_to_budget": metric.consent_gap_to_budget if metric else None,
            "real_gap_to_budget": metric.real_gap_to_budget if metric else None,
            "consent": row.consent,
        }
        directions.append(
            {
                "group_id": group.group_id,
                "name": group.name,
                "okso_code": group.okso_code,
                "seats": group.seats,
                "facts": facts,
            }
        )
    directions.sort(key=lambda item: (item["facts"]["priority"] or 999, item["facts"]["real_gap_to_budget"] or 9999))
    found = bool(directions)
    log = SearchLog(
        ip=ip,
        user_agent=user_agent,
        application_id=application_id,
        snapshot_id=snapshot.id,
        found=found,
        directions_count=len(directions),
        response_ms=int((time.perf_counter() - started) * 1000),
    )
    db.add(log)
    db.commit()
    return {
        "found": found,
        "application_id": application_id,
        "data_updated_at": snapshot.finished_at or snapshot.started_at,
        "deadline": settings.application_deadline_iso,
        "summary": {
            "directions_count": len(directions),
            "status": _summary_for_directions(directions),
        },
        "directions": directions,
    }
