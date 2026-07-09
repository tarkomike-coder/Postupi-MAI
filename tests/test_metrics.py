from __future__ import annotations

from datetime import datetime


def test_deferred_acceptance_moves_competitor_to_lower_priority_when_top_is_full():
    from backend.services.metrics import run_deferred_acceptance

    applicants = {
        "1001": [(1, 1, 300), (2, 2, 300)],
        "1002": [(1, 1, 310)],
        "1003": [(2, 1, 250)],
    }
    capacities = {1: 1, 2: 2}

    assert run_deferred_acceptance(applicants, capacities) == {
        "1001": 2,
        "1002": 1,
        "1003": 2,
    }


def test_compute_snapshot_metrics_counts_consent_and_real_competitors(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot
    from backend.services.metrics import compute_snapshot_metrics

    snapshot = Snapshot(status="running", started_at=datetime(2026, 7, 10, 9, 0))
    group = CompetitionGroup(
        group_id=501,
        okso_code="09.03.01",
        name="Информатика и вычислительная техника",
        education_level="Базовое высшее образование",
        education_form="Очная",
        place_type="Основные места в рамках КЦП",
        seats=2,
    )
    db_session.add_all([snapshot, group])
    db_session.flush()
    db_session.add_all(
        [
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1001",
                position=1,
                score=300,
                priority=1,
                consent=True,
                category="Общий конкурс",
            ),
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1002",
                position=2,
                score=290,
                priority=1,
                consent=True,
                category="Общий конкурс",
            ),
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1003",
                position=3,
                score=280,
                priority=1,
                consent=False,
                category="Общий конкурс",
            ),
        ]
    )
    db_session.commit()

    compute_snapshot_metrics(db_session, snapshot.id)

    metric = (
        db_session.query(ApplicantDailyMetric)
        .filter(
            ApplicantDailyMetric.snapshot_id == snapshot.id,
            ApplicantDailyMetric.application_id == "1003",
        )
        .one()
    )
    assert metric.position == 3
    assert metric.consent_position == 3
    assert metric.real_competitor_position == 3
    assert metric.above_with_consent == 2
    assert metric.above_without_consent == 0
    assert metric.real_gap_to_budget == 1
