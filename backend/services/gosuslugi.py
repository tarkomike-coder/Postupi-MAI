from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from ..config import settings

API_BASE = "https://www.gosuslugi.ru/api/university-applicant-list/v1/public/{year}"
ITEMS_URL = "https://www.gosuslugi.ru/api/vuz-navigator/public/v1/{year}/educational-programs/items"


class GosuslugiError(RuntimeError):
    pass


@dataclass(frozen=True)
class GroupItem:
    group_id: int
    okso_code: str | None
    name: str
    education_level: str | None
    education_form: str | None
    place_type: str | None
    seats: int | None


@dataclass(frozen=True)
class ApplicantItem:
    application_id: str
    position: int | None
    score: int | None
    priority: int | None
    consent: bool
    category: str | None = None


def normalize_okso(code: str | None) -> str | None:
    if not code:
        return None
    return code[2:] if code.startswith("2.") else code


def _to_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return score if score > 0 else None


def select_competition_groups(items: list[dict]) -> list[GroupItem]:
    selected = []
    for item in items:
        if item.get("educationLevelName") not in (
            "Базовое высшее образование",
            "Специализированное высшее образование",
        ):
            continue
        if item.get("educationFormName") != "Очная":
            continue
        if item.get("placeTypeName") != "Основные места в рамках КЦП":
            continue
        selected.append(
            GroupItem(
                group_id=int(item["id"]),
                okso_code=normalize_okso(item.get("oksoCode")),
                name=item.get("oksoName") or normalize_okso(item.get("oksoCode")) or str(item["id"]),
                education_level=item.get("educationLevelName"),
                education_form=item.get("educationFormName"),
                place_type=item.get("placeTypeName"),
                seats=item.get("numberPlaces"),
            )
        )
    return selected


def normalize_applicants(applicants: list[dict]) -> list[ApplicantItem]:
    rows = []
    for applicant in applicants:
        application_id = applicant.get("idApplication")
        score = _to_score(applicant.get("sumMark"))
        if application_id is None:
            continue
        rows.append(
            ApplicantItem(
                application_id=str(application_id),
                position=applicant.get("rating"),
                score=score,
                priority=applicant.get("priority"),
                consent=applicant.get("consent") not in (None, "NONE"),
                category=applicant.get("categoryName") or applicant.get("category"),
            )
        )
    return rows


class GosuslugiClient:
    def __init__(self, *, year: int | None = None, org_id: int | None = None):
        self.year = year or settings.gosuslugi_year
        self.org_id = org_id or settings.gosuslugi_org_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": f"https://www.gosuslugi.ru/vuznavigator/universities/{self.org_id}",
                "Accept": "application/json",
            }
        )

    def _request_json(self, method: str, url: str, **kwargs) -> Any:
        last_error: Exception | None = None
        for attempt in range(settings.request_retries):
            try:
                response = self.session.request(method, url, timeout=settings.request_timeout, **kwargs)
                if response.status_code == 200:
                    return response.json()
                last_error = GosuslugiError(f"HTTP {response.status_code}: {response.text[:300]}")
            except requests.RequestException as exc:
                last_error = exc
            time.sleep(0.5 * (attempt + 1))
        raise GosuslugiError(str(last_error))

    def fetch_program_items(self) -> list[dict]:
        result: list[dict] = []
        seen: set[int] = set()
        page = 0
        size = 500
        while True:
            items = self._request_json(
                "post",
                ITEMS_URL.format(year=self.year),
                params={"page": page, "size": size},
                json={"orgId": self.org_id},
            )
            if not items:
                break
            for item in items:
                item_id = item.get("id")
                if item_id in seen:
                    continue
                seen.add(item_id)
                result.append(item)
            page += 1
        return result

    def fetch_applicants(self, group_id: int) -> list[dict]:
        data = self._request_json(
            "get",
            f"{API_BASE.format(year=self.year)}/competition/{group_id}/applicants",
        )
        return data.get("applicants", [])
