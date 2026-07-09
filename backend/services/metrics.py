from __future__ import annotations

import heapq
from collections import defaultdict, deque
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, GroupStat

Applicants = dict[str, list[tuple[int, int, int]]]
Capacities = dict[int, int]


def run_deferred_acceptance(applicants: Applicants, capacities: Capacities) -> dict[str, int | None]:
    pointer = {code: 0 for code in applicants}
    heaps: dict[int, list[tuple[int, str]]] = {}
    free = deque(applicants.keys())

    while free:
        code = free.popleft()
        prefs = applicants[code]
        idx = pointer[code]
        while idx < len(prefs) and not capacities.get(prefs[idx][0]):
            idx += 1
        pointer[code] = idx
        if idx >= len(prefs):
            continue

        group_id, _priority, score = prefs[idx]
        heap = heaps.setdefault(group_id, [])
        heapq.heappush(heap, (score, code))
        if len(heap) > capacities[group_id]:
            _score, evicted = heapq.heappop(heap)
            pointer[evicted] += 1
            free.append(evicted)

    assignment: dict[str, int | None] = {code: None for code in applicants}
    for group_id, heap in heaps.items():
        for _score, code in heap:
            assignment[code] = group_id
    return assignment


@dataclass(frozen=True)
class _RowView:
    application_id: str
    group_id: int
    position: int | None
    score: int
    priority: int
    consent: bool


def _gap(position: int | None, seats: int | None) -> int | None:
    if position is None or seats is None:
        return None
    return max(0, position - seats)


def compute_snapshot_metrics(db: Session, snapshot_id: int) -> None:
    db.query(ApplicantDailyMetric).filter(ApplicantDailyMetric.snapshot_id == snapshot_id).delete()
    db.query(GroupStat).filter(GroupStat.snapshot_id == snapshot_id).delete()

    groups = {
        group.id: group
        for group in db.query(CompetitionGroup).all()
    }
    rows = (
        db.query(ApplicantRow)
        .filter(ApplicantRow.snapshot_id == snapshot_id, ApplicantRow.score.isnot(None), ApplicantRow.priority.isnot(None))
        .all()
    )
    views = [
        _RowView(
            application_id=row.application_id,
            group_id=row.group_id,
            position=row.position,
            score=int(row.score or 0),
            priority=int(row.priority or 999),
            consent=row.consent,
        )
        for row in rows
    ]

    by_group: dict[int, list[_RowView]] = defaultdict(list)
    by_applicant: dict[str, list[_RowView]] = defaultdict(list)
    for row in views:
        by_group[row.group_id].append(row)
        by_applicant[row.application_id].append(row)

    capacities = {gid: group.seats or 0 for gid, group in groups.items()}
    consented_applicants: Applicants = {}
    for application_id, applicant_rows in by_applicant.items():
        prefs = [
            (row.group_id, row.priority, row.score)
            for row in applicant_rows
            if row.consent and row.score
        ]
        if prefs:
            consented_applicants[application_id] = sorted(prefs, key=lambda item: item[1])

    assignment = run_deferred_acceptance(consented_applicants, capacities)
    real_competitors: dict[int, list[_RowView]] = defaultdict(list)
    for row in views:
        if assignment.get(row.application_id) == row.group_id:
            real_competitors[row.group_id].append(row)

    metrics = []
    for group_id, group_rows in by_group.items():
        ordered = sorted(group_rows, key=lambda row: (-(row.score or 0), row.position or 10**9))
        consent_ordered = [row for row in ordered if row.consent]
        real_ordered = sorted(real_competitors.get(group_id, []), key=lambda row: (-(row.score or 0), row.position or 10**9))
        scores = [row.score for row in ordered if row.score is not None]
        db.add(
            GroupStat(
                snapshot_id=snapshot_id,
                group_id=group_id,
                rows_count=len(group_rows),
                consent_count=len(consent_ordered),
                no_consent_count=len(group_rows) - len(consent_ordered),
                min_score=min(scores) if scores else None,
                max_score=max(scores) if scores else None,
            )
        )

        consent_rank = {row.application_id: idx + 1 for idx, row in enumerate(consent_ordered)}
        real_rank = {row.application_id: idx + 1 for idx, row in enumerate(real_ordered)}
        seats = groups.get(group_id).seats if groups.get(group_id) else None
        for idx, row in enumerate(ordered, start=1):
            above = ordered[: idx - 1]
            consent_position = consent_rank.get(row.application_id, len(consent_ordered) + 1)
            real_position = real_rank.get(row.application_id)
            if real_position is None:
                real_position = 1 + sum(1 for competitor in real_ordered if competitor.score > row.score)
            metrics.append(
                ApplicantDailyMetric(
                    snapshot_id=snapshot_id,
                    group_id=group_id,
                    application_id=row.application_id,
                    position=row.position or idx,
                    consent_position=consent_position,
                    real_competitor_position=real_position,
                    above_with_consent=sum(1 for item in above if item.consent),
                    above_without_consent=sum(1 for item in above if not item.consent),
                    general_gap_to_budget=_gap(row.position or idx, seats),
                    consent_gap_to_budget=_gap(consent_position, seats),
                    real_gap_to_budget=_gap(real_position, seats),
                )
            )
    db.bulk_save_objects(metrics)
    db.commit()
