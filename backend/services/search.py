from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from math import log10

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
        return "Приём документов завершён. Отображаем фактическое положение по последним данным."
    if any(item["facts"]["real_gap_to_budget"] == 0 for item in directions):
        return "Есть направления, где заявление сейчас внутри бюджетной зоны по текущим согласиям."
    if any((item["facts"]["real_gap_to_budget"] or 99) <= 5 for item in directions):
        return "Есть направления рядом с бюджетной зоной."
    return "Сейчас все найденные направления вне бюджетной зоны."


def _history(db: Session, application_id: str) -> list[dict]:
    rows = (
        db.query(ApplicantDailyMetric, CompetitionGroup, Snapshot)
        .join(CompetitionGroup, CompetitionGroup.id == ApplicantDailyMetric.group_id)
        .join(Snapshot, Snapshot.id == ApplicantDailyMetric.snapshot_id)
        .filter(ApplicantDailyMetric.application_id == application_id, Snapshot.status == "ok")
        .order_by(CompetitionGroup.name.asc(), Snapshot.started_at.asc(), Snapshot.id.asc())
        .all()
    )
    grouped: dict[int, dict] = {}
    for metric, group, snapshot in rows:
        entry = grouped.setdefault(
            group.id,
            {
                "group_id": group.group_id,
                "name": group.name,
                "okso_code": group.okso_code,
                "points": [],
            },
        )
        entry["points"].append(
            {
                "date": (snapshot.finished_at or snapshot.started_at).isoformat(),
                "position": metric.position,
                "consent_position": metric.consent_position,
                "real_competitor_position": metric.real_competitor_position,
                "above_with_consent": metric.above_with_consent,
                "above_without_consent": metric.above_without_consent,
                "real_gap_to_budget": metric.real_gap_to_budget,
            }
        )
    return list(grouped.values())


def _bounded_percent(value: int | float) -> int:
    return max(1, min(99, int(round(value))))


def _chance_from_gap(gap: int | None, *, seats: int | None, pending: int = 0) -> int:
    if gap is None:
        return 1
    seats_value = max(1, int(seats or 1))
    if gap <= 0:
        base = 94
    else:
        base = 88 - min(72, gap * max(3, round(18 / seats_value)))
    pressure = min(45, pending * max(2, round(10 / seats_value)))
    return _bounded_percent(base - pressure)


def _chance_if_pending_confirms(
    *,
    cascade_percent: int,
    pending: int,
    seats: int | None,
    real_position: int | None,
) -> int:
    if pending <= 0:
        return cascade_percent
    seats_value = max(1, int(seats or 1))
    current_position = max(1, int(real_position or seats_value + 1))
    cushion = max(0, seats_value - current_position + 1)
    scale_penalty = 18 * log10(pending + 1)
    density_penalty = min(22, (pending / seats_value) * 3)
    cushion_bonus = min(18, cushion * 0.35)
    penalty = max(0, scale_penalty + density_penalty - cushion_bonus)
    return _bounded_percent(cascade_percent - penalty)


def _chance_label(percent: int) -> str:
    if percent >= 85:
        return "высокая"
    if percent >= 60:
        return "хорошая"
    if percent >= 35:
        return "пограничная"
    return "низкая"


def _cascade_slice(metric: ApplicantDailyMetric | None) -> dict:
    if metric is None:
        return {
            "total_above": 0,
            "real_competitors_above": 0,
            "leaving_by_cascade": 0,
            "waiting_without_consent": 0,
        }
    above_with_consent = int(metric.above_with_consent or 0)
    above_without_consent = int(metric.above_without_consent or 0)
    real_competitors_above = max(0, int(metric.real_competitor_position or 1) - 1)
    return {
        "total_above": above_with_consent + above_without_consent,
        "real_competitors_above": real_competitors_above,
        "leaving_by_cascade": max(0, above_with_consent - real_competitors_above),
        "waiting_without_consent": above_without_consent,
    }


def _chance_block(metric: ApplicantDailyMetric | None, *, seats: int | None) -> dict:
    if metric is None:
        return {
            "current_percent": 1,
            "cascade_percent": 1,
            "tempo_percent": 1,
            "stress_percent": 1,
            "label": "нет оценки",
        }
    cascade = _cascade_slice(metric)
    current = _chance_from_gap(metric.consent_gap_to_budget, seats=seats)
    cascade_percent = _chance_from_gap(metric.real_gap_to_budget, seats=seats)
    stress = _chance_if_pending_confirms(
        cascade_percent=cascade_percent,
        pending=cascade["waiting_without_consent"],
        seats=seats,
        real_position=metric.real_competitor_position,
    )
    tempo = _bounded_percent((cascade_percent * 2 + stress + current) / 4)
    return {
        "current_percent": current,
        "cascade_percent": cascade_percent,
        "tempo_percent": tempo,
        "stress_percent": min(stress, cascade_percent),
        "label": _chance_label(tempo),
    }


def _score_at(rows: list[ApplicantRow], seats: int | None) -> int | None:
    if not rows or not seats:
        return None
    ordered = sorted(rows, key=lambda row: (-(row.score or 0), row.position or 10**9))
    if len(ordered) < seats:
        return None
    return ordered[seats - 1].score


def _cutoff_block(db: Session, *, snapshot_id: int, group_id: int, seats: int | None) -> dict:
    if not seats:
        return {"general": None, "consent": None, "cascade": None}
    rows = (
        db.query(ApplicantRow)
        .filter(
            ApplicantRow.snapshot_id == snapshot_id,
            ApplicantRow.group_id == group_id,
            ApplicantRow.score.isnot(None),
        )
        .all()
    )
    consent_rows = [row for row in rows if row.consent]
    cascade_rows = (
        db.query(ApplicantRow)
        .join(
            ApplicantDailyMetric,
            (ApplicantDailyMetric.snapshot_id == ApplicantRow.snapshot_id)
            & (ApplicantDailyMetric.group_id == ApplicantRow.group_id)
            & (ApplicantDailyMetric.application_id == ApplicantRow.application_id),
        )
        .filter(
            ApplicantRow.snapshot_id == snapshot_id,
            ApplicantRow.group_id == group_id,
            ApplicantDailyMetric.real_competitor_position <= seats,
            ApplicantRow.score.isnot(None),
        )
        .all()
    )
    return {
        "general": _score_at(rows, seats),
        "consent": _score_at(consent_rows, seats),
        "cascade": _score_at(cascade_rows, seats),
    }


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
                "chance": _chance_block(metric, seats=group.seats),
                "cascade": _cascade_slice(metric),
                "cutoff": _cutoff_block(db, snapshot_id=snapshot.id, group_id=group.id, seats=group.seats),
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
        "history": _history(db, application_id),
    }
