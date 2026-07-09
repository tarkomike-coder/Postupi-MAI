from __future__ import annotations


def test_selects_full_time_budget_groups_without_okso_allowlist():
    from backend.services.gosuslugi import select_competition_groups

    items = [
        {
            "id": 11,
            "oksoCode": "2.09.03.01",
            "oksoName": "Информатика и вычислительная техника",
            "educationLevelName": "Базовое высшее образование",
            "educationFormName": "Очная",
            "placeTypeName": "Основные места в рамках КЦП",
            "numberPlaces": 155,
        },
        {
            "id": 12,
            "oksoCode": "2.38.03.05",
            "oksoName": "Бизнес-информатика",
            "educationLevelName": "Базовое высшее образование",
            "educationFormName": "Очная",
            "placeTypeName": "Основные места в рамках КЦП",
            "numberPlaces": 24,
        },
        {
            "id": 13,
            "oksoCode": "2.09.03.02",
            "oksoName": "Платное",
            "educationLevelName": "Базовое высшее образование",
            "educationFormName": "Очная",
            "placeTypeName": "Платные места",
            "numberPlaces": 100,
        },
        {
            "id": 14,
            "oksoCode": "2.11.04.01",
            "oksoName": "Радиотехника",
            "educationLevelName": "Специализированное высшее образование",
            "educationFormName": "Очная",
            "placeTypeName": "Основные места в рамках КЦП",
            "numberPlaces": 12,
        },
        {
            "id": 15,
            "oksoCode": "2.3",
            "oksoName": "Аспирантура",
            "educationLevelName": "Аспирантура",
            "educationFormName": "Очная",
            "placeTypeName": "Основные места в рамках КЦП",
            "numberPlaces": 8,
        },
    ]

    selected = select_competition_groups(items)

    assert [item.group_id for item in selected] == [11, 12, 14]
    assert selected[0].okso_code == "09.03.01"
    assert selected[1].okso_code == "38.03.05"
    assert selected[2].okso_code == "11.04.01"


def test_normalizes_applicants_and_keeps_zero_scores_but_skips_missing_id():
    from backend.services.gosuslugi import normalize_applicants

    applicants = [
        {"idApplication": 1001, "rating": 1, "sumMark": 301.4, "priority": 1, "consent": "ONLINE"},
        {"idApplication": 1002, "rating": 2, "sumMark": 0, "priority": 1, "consent": "NONE"},
        {"rating": 3, "sumMark": 280, "priority": 1, "consent": "NONE"},
    ]

    rows = normalize_applicants(applicants)

    assert len(rows) == 2
    assert rows[0].application_id == "1001"
    assert rows[0].position == 1
    assert rows[0].score == 301
    assert rows[0].priority == 1
    assert rows[0].consent is True
    assert rows[1].application_id == "1002"
    assert rows[1].score is None


def test_fetch_program_items_paginates_and_deduplicates(monkeypatch):
    from backend.services.gosuslugi import GosuslugiClient

    calls = []

    class FakeSession:
        headers = {}

        def request(self, method, url, timeout, **kwargs):
            del method, url, timeout
            page = kwargs["params"]["page"]
            calls.append(page)

            class Response:
                status_code = 200
                text = ""

                def json(self_inner):
                    if page == 0:
                        return [{"id": 1}, {"id": 2}]
                    if page == 1:
                        return [{"id": 2}, {"id": 3}]
                    return []

            return Response()

    monkeypatch.setattr("requests.Session", FakeSession)

    client = GosuslugiClient(org_id=26)

    assert client.fetch_program_items() == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert calls == [0, 1, 2]
