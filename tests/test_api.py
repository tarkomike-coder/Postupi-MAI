from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient


def seed_result(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot

    snapshot = Snapshot(status="ok", started_at=datetime(2026, 7, 10, 9, 0), finished_at=datetime(2026, 7, 10, 9, 5))
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
    db_session.add(
        ApplicantRow(
            snapshot_id=snapshot.id,
            group_id=group.id,
            application_id="1001",
            position=3,
            score=280,
            priority=1,
            consent=False,
            category="Общий конкурс",
        )
    )
    db_session.add(
        ApplicantDailyMetric(
            snapshot_id=snapshot.id,
            group_id=group.id,
            application_id="1001",
            position=3,
            consent_position=3,
            real_competitor_position=3,
            above_with_consent=2,
            above_without_consent=0,
            general_gap_to_budget=1,
            consent_gap_to_budget=1,
            real_gap_to_budget=1,
        )
    )
    db_session.commit()


def build_client(db_session):
    from backend.main import create_app
    from backend.api import get_db

    app = create_app(mount_static=False)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_status_returns_timezone_aware_update_time(db_session):
    from backend.models import Snapshot

    db_session.add(
        Snapshot(
            status="ok",
            started_at=datetime(2026, 7, 9, 15, 30, 0),
            finished_at=datetime(2026, 7, 9, 15, 33, 30, 316465),
            groups_count=49,
            rows_count=45789,
            unique_applications_count=12029,
        )
    )
    db_session.commit()

    response = build_client(db_session).get("/api/status")

    assert response.status_code == 200
    assert response.json()["updated_at"] == "2026-07-09T15:33:30.316465Z"


def test_search_returns_directions_and_logs_request(db_session):
    from backend.models import SearchLog

    seed_result(db_session)
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "1001"}, headers={"X-Forwarded-For": "1.2.3.4"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["application_id"] == "1001"
    assert body["summary"]["directions_count"] == 1
    assert body["directions"][0]["name"] == "Информатика и вычислительная техника"
    assert body["directions"][0]["facts"]["score"] == 280
    assert db_session.query(SearchLog).count() == 1
    assert db_session.query(SearchLog).one().found is True


def test_search_not_found_is_logged(db_session):
    from backend.models import SearchLog

    seed_result(db_session)
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "9999"}, headers={"X-Forwarded-For": "1.2.3.4"})

    assert response.status_code == 200
    assert response.json()["found"] is False
    log = db_session.query(SearchLog).one()
    assert log.application_id == "9999"
    assert log.found is False


def test_search_rate_limits_many_distinct_numbers(db_session, monkeypatch):
    seed_result(db_session)
    monkeypatch.setattr("backend.services.search.settings.search_limit_distinct", 2)
    monkeypatch.setattr("backend.services.search.settings.search_limit_total", 10)
    client = build_client(db_session)

    assert client.post("/api/search", json={"application_id": "2001"}, headers={"X-Forwarded-For": "5.5.5.5"}).status_code == 200
    assert client.post("/api/search", json={"application_id": "2002"}, headers={"X-Forwarded-For": "5.5.5.5"}).status_code == 200
    limited = client.post("/api/search", json={"application_id": "2003"}, headers={"X-Forwarded-For": "5.5.5.5"})

    assert limited.status_code == 429
    assert limited.json()["error"] == "rate_limited"
    assert limited.json()["retry_after_seconds"] > 0


def test_search_includes_history_points(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot

    first = Snapshot(status="ok", started_at=datetime(2026, 7, 9, 9, 0), finished_at=datetime(2026, 7, 9, 9, 5))
    second = Snapshot(status="ok", started_at=datetime(2026, 7, 10, 9, 0), finished_at=datetime(2026, 7, 10, 9, 5))
    group = CompetitionGroup(group_id=777, okso_code="09.03.02", name="Информационные системы", seats=1)
    db_session.add_all([first, second, group])
    db_session.flush()
    for snapshot, position in [(first, 5), (second, 3)]:
        db_session.add(
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1007",
                position=position,
                score=270,
                priority=1,
                consent=False,
            )
        )
        db_session.add(
            ApplicantDailyMetric(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1007",
                position=position,
                consent_position=position,
                real_competitor_position=position,
                above_with_consent=position - 1,
                above_without_consent=0,
                general_gap_to_budget=position - 1,
                consent_gap_to_budget=position - 1,
                real_gap_to_budget=position - 1,
            )
        )
    db_session.commit()
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "1007"})

    assert response.status_code == 200
    history = response.json()["history"]
    assert len(history) == 1
    assert [point["position"] for point in history[0]["points"]] == [5, 3]


def test_search_includes_chances_and_global_cascade_slice(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot

    snapshot = Snapshot(status="ok", started_at=datetime(2026, 7, 10, 9, 0), finished_at=datetime(2026, 7, 10, 9, 5))
    group = CompetitionGroup(group_id=888, okso_code="09.03.03", name="Прикладная информатика", seats=2)
    db_session.add_all([snapshot, group])
    db_session.flush()
    for application_id, position, score, consent in [
        ("2001", 1, 300, True),
        ("2002", 2, 295, True),
        ("2003", 3, 290, False),
        ("1001", 4, 280, False),
    ]:
        db_session.add(
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id=application_id,
                position=position,
                score=score,
                priority=1,
                consent=consent,
            )
        )
    db_session.add(
        ApplicantDailyMetric(
            snapshot_id=snapshot.id,
            group_id=group.id,
            application_id="1001",
            position=4,
            consent_position=3,
            real_competitor_position=2,
            above_with_consent=2,
            above_without_consent=1,
            general_gap_to_budget=2,
            consent_gap_to_budget=1,
            real_gap_to_budget=0,
        )
    )
    db_session.commit()
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "1001"})

    assert response.status_code == 200
    direction = response.json()["directions"][0]
    assert set(direction["chance"]) == {
        "current_percent",
        "cascade_percent",
        "tempo_percent",
        "stress_percent",
        "label",
    }
    assert direction["cascade"] == {
        "total_above": 3,
        "real_competitors_above": 1,
        "leaving_by_cascade": 1,
        "waiting_without_consent": 1,
    }
    assert direction["chance"]["cascade_percent"] >= direction["chance"]["stress_percent"]


def test_prediction_chooses_passing_direction_by_selected_priority(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot

    snapshot = Snapshot(status="ok", started_at=datetime(2026, 7, 10, 9, 0), finished_at=datetime(2026, 7, 10, 9, 5))
    lower_priority = CompetitionGroup(group_id=901, okso_code="09.03.01", name="Нижний приоритет", seats=2)
    higher_priority = CompetitionGroup(group_id=902, okso_code="09.03.02", name="Высший приоритет", seats=2)
    db_session.add_all([snapshot, lower_priority, higher_priority])
    db_session.flush()
    for group, priority, real_position in [(lower_priority, 2, 1), (higher_priority, 1, 2)]:
        db_session.add(
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1001",
                position=10,
                score=280,
                priority=priority,
                consent=True,
            )
        )
        db_session.add(
            ApplicantDailyMetric(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1001",
                position=10,
                consent_position=2,
                real_competitor_position=real_position,
                above_with_consent=1,
                above_without_consent=5,
                general_gap_to_budget=8,
                consent_gap_to_budget=0,
                real_gap_to_budget=0,
            )
        )
    db_session.commit()
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "1001"})

    assert response.status_code == 200
    prediction = response.json()["prediction"]
    assert prediction["status"] == "passing"
    assert prediction["name"] == "Высший приоритет"
    assert prediction["priority"] == 1
    assert prediction["needed_places"] == 0


def test_prediction_reports_closest_direction_when_none_passes(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot

    snapshot = Snapshot(status="ok", started_at=datetime(2026, 7, 10, 9, 0), finished_at=datetime(2026, 7, 10, 9, 5))
    far = CompetitionGroup(group_id=911, name="Далеко", seats=2)
    close = CompetitionGroup(group_id=912, name="Ближе", seats=2)
    db_session.add_all([snapshot, far, close])
    db_session.flush()
    for group, gap in [(far, 8), (close, 2)]:
        db_session.add(
            ApplicantRow(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1001",
                position=20,
                score=260,
                priority=1,
                consent=False,
            )
        )
        db_session.add(
            ApplicantDailyMetric(
                snapshot_id=snapshot.id,
                group_id=group.id,
                application_id="1001",
                position=20,
                consent_position=15,
                real_competitor_position=(group.seats or 2) + gap,
                above_with_consent=10,
                above_without_consent=20,
                general_gap_to_budget=18,
                consent_gap_to_budget=13,
                real_gap_to_budget=gap,
            )
        )
    db_session.commit()
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "1001"})

    assert response.status_code == 200
    prediction = response.json()["prediction"]
    assert prediction["status"] == "not_passing"
    assert prediction["name"] == "Ближе"
    assert prediction["needed_places"] == 2


def test_pending_without_consent_scenario_varies_by_direction_pressure():
    from backend.services.search import _chance_block

    lower_pressure = SimpleNamespace(
        consent_gap_to_budget=0,
        real_gap_to_budget=0,
        above_with_consent=10,
        above_without_consent=64,
        real_competitor_position=1,
    )
    higher_pressure = SimpleNamespace(
        consent_gap_to_budget=0,
        real_gap_to_budget=0,
        above_with_consent=10,
        above_without_consent=355,
        real_competitor_position=1,
    )

    low = _chance_block(lower_pressure, seats=75)
    high = _chance_block(higher_pressure, seats=155)

    assert high["stress_percent"] < low["stress_percent"]
    assert high["stress_percent"] != low["stress_percent"]
