from __future__ import annotations

from datetime import datetime

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
