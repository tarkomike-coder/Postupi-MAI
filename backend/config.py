from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'mai_local.db'}",
    )
    raw_snapshots_dir: Path = Path(
        os.environ.get("RAW_SNAPSHOTS_DIR", PROJECT_ROOT / "data" / "raw")
    )
    gosuslugi_year: int = int(os.environ.get("GOSUSLUGI_YEAR", "2026"))
    gosuslugi_org_id: int = int(os.environ.get("GOSUSLUGI_ORG_ID", "19"))
    request_timeout: int = int(os.environ.get("REQUEST_TIMEOUT", "20"))
    request_retries: int = int(os.environ.get("REQUEST_RETRIES", "3"))
    search_window_minutes: int = int(os.environ.get("SEARCH_WINDOW_MINUTES", "10"))
    search_limit_total: int = int(os.environ.get("SEARCH_LIMIT_TOTAL", "20"))
    search_limit_distinct: int = int(os.environ.get("SEARCH_LIMIT_DISTINCT", "10"))
    search_cooldown_minutes: int = int(os.environ.get("SEARCH_COOLDOWN_MINUTES", "15"))
    application_deadline_iso: str = os.environ.get(
        "APPLICATION_DEADLINE_ISO",
        "2026-07-25T17:00:00+03:00",
    )
    admin_token: str | None = os.environ.get("MAI_ADMIN_TOKEN")


settings = Settings()
