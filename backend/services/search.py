from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import log10

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, GroupStat, SearchLog, Snapshot, utcnow
from .metrics import run_deferred_acceptance


@dataclass(frozen=True)
class SearchRateLimited(Exception):
    retry_after_seconds: int


def _window_start():
    return utcnow() - timedelta(minutes=settings.search_window_minutes)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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
        "updated_at": _as_utc(snapshot.finished_at or snapshot.started_at),
        "groups_count": snapshot.groups_count,
        "rows_count": snapshot.rows_count,
        "unique_applications_count": snapshot.unique_applications_count,
    }


def _round_per_place(rows_count: int, seats: int | None) -> float | None:
    if not seats:
        return None
    return round(rows_count / seats, 1)


def _direction_dashboard_item(
    *,
    group: CompetitionGroup,
    rows: list[tuple[ApplicantRow, ApplicantDailyMetric | None]],
    stat: GroupStat | None,
    assignment: dict[str, int | None],
) -> dict:
    seats = group.seats or 0
    applicant_rows = [row for row, _metric in rows]
    rows_count = stat.rows_count if stat else len(applicant_rows)
    consent_count = stat.consent_count if stat else sum(1 for row in applicant_rows if row.consent)
    consent_rows = [row for row in applicant_rows if row.consent]
    cascade_rows = [
        row
        for row, metric in rows
        if seats and row.consent and assignment.get(row.application_id) == row.group_id
    ]
    return {
        "group_id": group.group_id,
        "name": group.name,
        "okso_code": group.okso_code,
        "seats": group.seats,
        "applicants_count": rows_count,
        "consent_count": consent_count,
        "applicants_per_place": _round_per_place(rows_count, group.seats),
        "cascade_in_budget_count": min(len(cascade_rows), seats) if seats else 0,
        "no_consent_in_cascade": sum(1 for row in cascade_rows if not row.consent),
        "cutoff": {
            "general": _score_at(applicant_rows, group.seats),
            "consent": _score_at(consent_rows, group.seats),
            "cascade": _score_at(cascade_rows, group.seats),
        },
    }


def _snapshot_assignment(db: Session, snapshot_id: int) -> dict[str, int | None]:
    rows = (
        db.query(ApplicantRow)
        .filter(
            ApplicantRow.snapshot_id == snapshot_id,
            ApplicantRow.score.isnot(None),
            ApplicantRow.priority.isnot(None),
            ApplicantRow.consent.is_(True),
        )
        .all()
    )
    group_ids = sorted({row.group_id for row in rows})
    if not group_ids:
        return {}
    capacities = {
        group.id: group.seats or 0
        for group in db.query(CompetitionGroup).filter(CompetitionGroup.id.in_(group_ids)).all()
    }
    applicants: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for row in rows:
        applicants[row.application_id].append((row.group_id, int(row.priority or 999), int(row.score or 0)))
    return run_deferred_acceptance(
        {application_id: sorted(prefs, key=lambda item: item[1]) for application_id, prefs in applicants.items()},
        capacities,
    )


def _sort_value(value, fallback=0):
    return fallback if value is None else value


def build_overview_response(db: Session) -> dict:
    snapshot = _latest_ok_snapshot(db)
    if snapshot is None:
        return {
            "has_data": False,
            "updated_at": None,
            "source": "public_gosuslugi",
            "source_text": "Данные рассчитываются только по публичным конкурсным спискам Госуслуг.",
            "totals": {
                "directions_count": 0,
                "budget_places": 0,
                "applicants_count": 0,
                "consents_count": 0,
            },
            "cascade": [],
            "cutoffs": [],
            "competition": [],
        }

    current_group_ids = [
        group_id
        for (group_id,) in db.query(ApplicantRow.group_id).filter(ApplicantRow.snapshot_id == snapshot.id).distinct().all()
    ]
    group_rows = (
        db.query(CompetitionGroup, GroupStat)
        .outerjoin(
            GroupStat,
            (GroupStat.group_id == CompetitionGroup.id) & (GroupStat.snapshot_id == snapshot.id),
        )
        .filter(CompetitionGroup.id.in_(current_group_ids))
        .order_by(CompetitionGroup.name.asc())
        .all()
    )
    applicant_rows = (
        db.query(ApplicantRow, ApplicantDailyMetric)
        .outerjoin(
            ApplicantDailyMetric,
            (ApplicantDailyMetric.snapshot_id == ApplicantRow.snapshot_id)
            & (ApplicantDailyMetric.group_id == ApplicantRow.group_id)
            & (ApplicantDailyMetric.application_id == ApplicantRow.application_id),
        )
        .filter(ApplicantRow.snapshot_id == snapshot.id)
        .all()
    )
    rows_by_group: dict[int, list[tuple[ApplicantRow, ApplicantDailyMetric | None]]] = {}
    for row, metric in applicant_rows:
        rows_by_group.setdefault(row.group_id, []).append((row, metric))

    assignment = _snapshot_assignment(db, snapshot.id)
    directions = [
        _direction_dashboard_item(group=group, rows=rows_by_group.get(group.id, []), stat=stat, assignment=assignment)
        for group, stat in group_rows
    ]
    budget_places = sum(int(item["seats"] or 0) for item in directions)
    consents_count = sum(int(item["consent_count"] or 0) for item in directions)

    cascade = sorted(
        directions,
        key=lambda item: (
            _sort_value(item["applicants_count"]),
            _sort_value(item["seats"]),
            item["name"],
        ),
        reverse=True,
    )[:8]
    cutoffs = sorted(
        directions,
        key=lambda item: (
            _sort_value(item["cutoff"]["cascade"], -1),
            _sort_value(item["cutoff"]["consent"], -1),
            _sort_value(item["applicants_count"]),
        ),
        reverse=True,
    )[:8]
    competition = sorted(
        [item for item in directions if item["applicants_per_place"] is not None],
        key=lambda item: (
            _sort_value(item["applicants_per_place"]),
            _sort_value(item["applicants_count"]),
        ),
        reverse=True,
    )[:10]

    return {
        "has_data": True,
        "updated_at": _as_utc(snapshot.finished_at or snapshot.started_at),
        "source": "public_gosuslugi",
        "source_text": "Данные рассчитываются только по публичным конкурсным спискам Госуслуг.",
        "totals": {
            "directions_count": snapshot.groups_count or len(directions),
            "budget_places": budget_places,
            "applicants_count": snapshot.unique_applications_count or snapshot.rows_count,
            "consents_count": consents_count,
        },
        "directions": directions,
        "cascade": cascade,
        "cutoffs": cutoffs,
        "competition": competition,
    }


def _direction_history_point(
    *,
    snapshot: Snapshot,
    group: CompetitionGroup,
    rows: list[tuple[ApplicantRow, ApplicantDailyMetric | None]],
    stat: GroupStat | None,
    assignment: dict[str, int | None],
) -> dict:
    item = _direction_dashboard_item(group=group, rows=rows, stat=stat, assignment=assignment)
    return {
        "date": _as_utc(snapshot.finished_at or snapshot.started_at),
        "applicants_count": item["applicants_count"],
        "consent_count": item["consent_count"],
        "applicants_per_place": item["applicants_per_place"],
        "calculated_budget_score": item["cutoff"]["cascade"],
        "calculated_competitors_count": len(
            [row for row, _metric in rows if row.consent and assignment.get(row.application_id) == group.id]
        ),
    }


def build_direction_response(db: Session, *, group_id: int) -> dict:
    group = db.query(CompetitionGroup).filter(CompetitionGroup.group_id == group_id).first()
    if group is None:
        return {"found": False, "group_id": group_id}

    snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.status == "ok")
        .order_by(Snapshot.started_at.asc(), Snapshot.id.asc())
        .all()
    )
    if not snapshots:
        return {"found": False, "group_id": group_id, "name": group.name}

    latest = snapshots[-1]
    latest_rows = (
        db.query(ApplicantRow, ApplicantDailyMetric)
        .outerjoin(
            ApplicantDailyMetric,
            (ApplicantDailyMetric.snapshot_id == ApplicantRow.snapshot_id)
            & (ApplicantDailyMetric.group_id == ApplicantRow.group_id)
            & (ApplicantDailyMetric.application_id == ApplicantRow.application_id),
        )
        .filter(ApplicantRow.snapshot_id == latest.id, ApplicantRow.group_id == group.id)
        .all()
    )
    latest_stat = (
        db.query(GroupStat)
        .filter(GroupStat.snapshot_id == latest.id, GroupStat.group_id == group.id)
        .first()
    )
    latest_assignment = _snapshot_assignment(db, latest.id)
    summary = _direction_dashboard_item(group=group, rows=latest_rows, stat=latest_stat, assignment=latest_assignment)
    assigned_rows = sorted(
        [
            row
            for row, _metric in latest_rows
            if row.consent and latest_assignment.get(row.application_id) == group.id
        ],
        key=lambda row: (-(row.score or 0), row.position or 10**9, row.application_id),
    )
    applicants = []
    seats = group.seats or 0
    for index, row in enumerate(assigned_rows, start=1):
        if seats and index <= seats:
            status = "в пределах бюджета"
        elif seats and index == seats + 1:
            status = "следующий после бюджета"
        else:
            status = "ниже бюджета"
        applicants.append(
            {
                "calculated_position": index,
                "application_id": row.application_id,
                "score": row.score,
                "priority": row.priority,
                "source_position": row.position,
                "status": status,
            }
        )

    history = []
    for snapshot in snapshots:
        rows = (
            db.query(ApplicantRow, ApplicantDailyMetric)
            .outerjoin(
                ApplicantDailyMetric,
                (ApplicantDailyMetric.snapshot_id == ApplicantRow.snapshot_id)
                & (ApplicantDailyMetric.group_id == ApplicantRow.group_id)
                & (ApplicantDailyMetric.application_id == ApplicantRow.application_id),
            )
            .filter(ApplicantRow.snapshot_id == snapshot.id, ApplicantRow.group_id == group.id)
            .all()
        )
        if not rows:
            continue
        stat = (
            db.query(GroupStat)
            .filter(GroupStat.snapshot_id == snapshot.id, GroupStat.group_id == group.id)
            .first()
        )
        history.append(
            _direction_history_point(
                snapshot=snapshot,
                group=group,
                rows=rows,
                stat=stat,
                assignment=_snapshot_assignment(db, snapshot.id),
            )
        )

    return {
        "found": True,
        "group_id": group.group_id,
        "name": group.name,
        "okso_code": group.okso_code,
        "seats": group.seats,
        "updated_at": _as_utc(latest.finished_at or latest.started_at),
        "summary": summary,
        "history": history,
        "applicants": applicants,
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
        return "Код поступающего не найден в очных бюджетных конкурсах МАИ."
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
                "date": _as_utc(snapshot.finished_at or snapshot.started_at).isoformat(),
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


def _prediction(directions: list[dict]) -> dict | None:
    if not directions:
        return None

    def _item_payload(item: dict, status: str) -> dict:
        facts = item["facts"]
        gap = facts.get("real_gap_to_budget")
        return {
            "status": status,
            "group_id": item["group_id"],
            "name": item["name"],
            "okso_code": item["okso_code"],
            "priority": facts.get("priority"),
            "seats": item["seats"],
            "chance_percent": item.get("chance", {}).get("cascade_percent"),
            "needed_places": 0 if gap is None else max(0, gap),
        }

    passing = [item for item in directions if item["facts"].get("real_gap_to_budget") == 0]
    if passing:
        selected = sorted(
            passing,
            key=lambda item: (
                item["facts"].get("priority") or 999,
                item["facts"].get("real_competitor_position") or 9999,
            ),
        )[0]
        return _item_payload(selected, "passing")

    selected = sorted(
        directions,
        key=lambda item: (
            item["facts"].get("real_gap_to_budget") if item["facts"].get("real_gap_to_budget") is not None else 9999,
            item["facts"].get("priority") or 999,
        ),
    )[0]
    return _item_payload(selected, "not_passing")


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
        "data_updated_at": _as_utc(snapshot.finished_at or snapshot.started_at),
        "deadline": settings.application_deadline_iso,
        "summary": {
            "directions_count": len(directions),
            "status": _summary_for_directions(directions),
        },
        "prediction": _prediction(directions),
        "directions": directions,
        "history": _history(db, application_id),
    }
