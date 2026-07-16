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
    from backend.api import get_db
    from backend.main import create_app

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


def test_overview_returns_gosuslugi_dashboard_from_latest_snapshot(db_session):
    from backend.models import ApplicantDailyMetric, ApplicantRow, CompetitionGroup, Snapshot

    snapshot = Snapshot(
        status="ok",
        started_at=datetime(2026, 7, 10, 9, 0),
        finished_at=datetime(2026, 7, 10, 9, 5),
        groups_count=2,
        rows_count=5,
        unique_applications_count=5,
    )
    first = CompetitionGroup(group_id=601, okso_code="09.03.01", name="Информатика", seats=2)
    second = CompetitionGroup(group_id=602, okso_code="09.03.04", name="Программная инженерия", seats=1)
    stale = CompetitionGroup(group_id=603, okso_code="11.03.01", name="Старое направление", seats=99)
    db_session.add_all([snapshot, first, second, stale])
    db_session.flush()

    for group, rows in [
        (first, [("1001", 1, 300, True), ("1002", 2, 290, False), ("1003", 3, 280, False)]),
        (second, [("2001", 1, 310, True), ("2002", 2, 270, False)]),
    ]:
        for application_id, position, score, consent in rows:
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
                    application_id=application_id,
                    position=position,
                    consent_position=position,
                    real_competitor_position=position,
                    above_with_consent=max(0, position - 1),
                    above_without_consent=0,
                    general_gap_to_budget=max(0, position - (group.seats or 0)),
                    consent_gap_to_budget=max(0, position - (group.seats or 0)),
                    real_gap_to_budget=max(0, position - (group.seats or 0)),
                )
            )
    db_session.commit()

    response = build_client(db_session).get("/api/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "public_gosuslugi"
    assert body["totals"] == {
        "directions_count": 2,
        "budget_places": 3,
        "applicants_count": 5,
        "consents_count": 2,
    }
    assert body["cascade"][0]["name"] == "Информатика"
    assert body["cascade"][0]["cascade_in_budget_count"] == 1
    assert body["cascade"][0]["no_consent_in_cascade"] == 0
    assert body["cascade"][0]["cutoff"]["general"] == 290
    assert body["cascade"][0]["cutoff"]["cascade"] is None
    competition_by_name = {item["name"]: item for item in body["competition"]}
    assert competition_by_name["Информатика"]["applicants_per_place"] == 1.5
    assert competition_by_name["Программная инженерия"]["applicants_per_place"] == 2.0


def test_direction_page_returns_history_and_assigned_consent_applicants_only(db_session):
    from backend.models import ApplicantRow, CompetitionGroup, Snapshot

    first_snapshot = Snapshot(
        status="ok",
        started_at=datetime(2026, 7, 9, 9, 0),
        finished_at=datetime(2026, 7, 9, 9, 5),
        groups_count=2,
        rows_count=4,
        unique_applications_count=3,
    )
    latest_snapshot = Snapshot(
        status="ok",
        started_at=datetime(2026, 7, 10, 9, 0),
        finished_at=datetime(2026, 7, 10, 9, 5),
        groups_count=2,
        rows_count=4,
        unique_applications_count=3,
    )
    target = CompetitionGroup(group_id=701, okso_code="09.03.01", name="Информатика", seats=1)
    higher = CompetitionGroup(group_id=702, okso_code="09.03.04", name="Программная инженерия", seats=1)
    db_session.add_all([first_snapshot, latest_snapshot, target, higher])
    db_session.flush()

    for snapshot, target_score in [(first_snapshot, 280), (latest_snapshot, 290)]:
        for group, application_id, score, priority, consent, position in [
            (target, "1001", 300, 2, True, 1),
            (higher, "1001", 300, 1, True, 1),
            (target, "1002", target_score, 1, True, 2),
            (target, "1003", 310, 1, False, 3),
        ]:
            db_session.add(
                ApplicantRow(
                    snapshot_id=snapshot.id,
                    group_id=group.id,
                    application_id=application_id,
                    position=position,
                    score=score,
                    priority=priority,
                    consent=consent,
                )
            )
    db_session.commit()

    response = build_client(db_session).get("/api/directions/701")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["summary"]["cutoff"]["cascade"] == 290
    assert [point["calculated_budget_score"] for point in body["history"]] == [280, 290]
    assert [item["application_id"] for item in body["applicants"]] == ["1002"]
    assert body["applicants"][0]["status"] == "в пределах бюджета"


def test_search_normalizes_formatted_application_id(db_session):
    from backend.models import SearchLog

    seed_result(db_session)
    client = build_client(db_session)

    response = client.post("/api/search", json={"application_id": "№ 1 001"}, headers={"X-Forwarded-For": "1.2.3.4"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["application_id"] == "1001"
    assert db_session.query(SearchLog).one().application_id == "1001"


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
