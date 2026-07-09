from __future__ import annotations


class FakeClient:
    def fetch_program_items(self):
        return [
            {
                "id": 501,
                "oksoCode": "2.09.03.01",
                "oksoName": "Информатика и вычислительная техника",
                "educationLevelName": "Базовое высшее образование",
                "educationFormName": "Очная",
                "placeTypeName": "Основные места в рамках КЦП",
                "numberPlaces": 2,
            }
        ]

    def fetch_applicants(self, group_id: int):
        assert group_id == 501
        return [
            {"idApplication": 1001, "rating": 1, "sumMark": 300, "priority": 1, "consent": "ONLINE"},
            {"idApplication": 1002, "rating": 2, "sumMark": 290, "priority": 1, "consent": "NONE"},
        ]


def test_import_snapshot_stores_rows_and_metrics(db_session, tmp_path):
    from backend.models import ApplicantDailyMetric, ApplicantRow, Snapshot
    from backend.services.importer import import_snapshot

    snapshot = import_snapshot(db_session, client=FakeClient(), raw_dir=tmp_path)

    assert snapshot.status == "ok"
    assert snapshot.groups_count == 1
    assert snapshot.rows_count == 2
    assert snapshot.unique_applications_count == 2
    assert db_session.query(ApplicantRow).count() == 2
    assert db_session.query(ApplicantDailyMetric).count() == 2
    assert db_session.query(Snapshot).count() == 1
    assert snapshot.raw_path is not None
    assert tmp_path.joinpath(snapshot.raw_path).exists()


class FakeBaumanClient:
    def fetch_program_items(self):
        return [
            {
                "id": 901,
                "oksoCode": "2.09.03.01",
                "oksoName": "Информатика и вычислительная техника",
                "educationLevelName": "Базовое высшее образование",
                "educationFormName": "Очная",
                "placeTypeName": "Основные места в рамках КЦП",
                "numberPlaces": 204,
            }
        ]

    def fetch_applicants(self, group_id: int):
        assert group_id == 901
        return [
            {"idApplication": 3001, "rating": 1, "sumMark": 301, "priority": 1, "consent": "ONLINE"},
            {"idApplication": 3002, "rating": 2, "sumMark": 290, "priority": 2, "consent": "NONE"},
        ]


def test_import_bauman_snapshot_stores_full_daily_rows(db_session, tmp_path):
    from backend.models import BaumanApplicantRow, BaumanCompetitionGroup, BaumanSnapshot
    from backend.services.bauman_importer import import_bauman_snapshot

    snapshot = import_bauman_snapshot(db_session, client=FakeBaumanClient(), raw_dir=tmp_path)

    assert snapshot.status == "ok"
    assert snapshot.groups_count == 1
    assert snapshot.rows_count == 2
    assert snapshot.unique_applications_count == 2
    assert db_session.query(BaumanSnapshot).count() == 1
    assert db_session.query(BaumanCompetitionGroup).count() == 1
    assert db_session.query(BaumanApplicantRow).count() == 2
    assert snapshot.raw_path is not None
    assert tmp_path.joinpath(snapshot.raw_path).exists()
