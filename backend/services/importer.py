from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import ApplicantRow, CompetitionGroup, Snapshot
from .gosuslugi import GosuslugiClient, GosuslugiError, normalize_applicants, select_competition_groups
from .metrics import compute_snapshot_metrics


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_or_create_group(db: Session, item) -> CompetitionGroup:
    group = db.query(CompetitionGroup).filter(CompetitionGroup.group_id == item.group_id).first()
    if group is None:
        group = CompetitionGroup(group_id=item.group_id, name=item.name)
        db.add(group)
        db.flush()
    group.okso_code = item.okso_code
    group.name = item.name
    group.education_level = item.education_level
    group.education_form = item.education_form
    group.place_type = item.place_type
    group.seats = item.seats
    return group


def _write_raw(raw_dir: Path, snapshot_id: int, payload: dict) -> str:
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = f"mai_snapshot_{snapshot_id}.json.gz"
    path = raw_dir / name
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return name


def import_snapshot(
    db: Session,
    *,
    client: GosuslugiClient | None = None,
    raw_dir: Path | None = None,
    trigger: str = "manual",
) -> Snapshot:
    del trigger
    client = client or GosuslugiClient()
    raw_dir = raw_dir or settings.raw_snapshots_dir
    snapshot = Snapshot(status="running", started_at=_now())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    raw_payload: dict = {"groups": [], "applicants": {}}
    try:
        group_items = select_competition_groups(client.fetch_program_items())
        raw_payload["groups"] = [item.__dict__ for item in group_items]
        unique_applications: set[str] = set()
        rows_count = 0
        for item in group_items:
            applicants_raw = client.fetch_applicants(item.group_id)
            raw_payload["applicants"][str(item.group_id)] = applicants_raw
            applicants = normalize_applicants(applicants_raw)
            group = _get_or_create_group(db, item)
            db.flush()
            for applicant in applicants:
                unique_applications.add(applicant.application_id)
                rows_count += 1
                db.add(
                    ApplicantRow(
                        snapshot_id=snapshot.id,
                        group_id=group.id,
                        application_id=applicant.application_id,
                        position=applicant.position,
                        score=applicant.score,
                        priority=applicant.priority,
                        consent=applicant.consent,
                        category=applicant.category,
                    )
                )
        snapshot.groups_count = len(group_items)
        snapshot.rows_count = rows_count
        snapshot.unique_applications_count = len(unique_applications)
        snapshot.raw_path = _write_raw(raw_dir, snapshot.id, raw_payload)
        db.commit()
        compute_snapshot_metrics(db, snapshot.id)
        snapshot.status = "ok"
    except (GosuslugiError, Exception) as exc:
        db.rollback()
        snapshot = db.get(Snapshot, snapshot.id)
        snapshot.status = "error"
        snapshot.error_message = f"{type(exc).__name__}: {exc}"[:2000]
    finally:
        snapshot.finished_at = _now()
        db.commit()
        db.refresh(snapshot)
    return snapshot
