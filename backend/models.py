from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Snapshot(Base):
    __tablename__ = "mai_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    groups_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_applications_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CompetitionGroup(Base):
    __tablename__ = "mai_competition_groups"
    __table_args__ = (UniqueConstraint("group_id", name="uq_mai_group_gosuslugi_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    okso_code: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    education_level: Mapped[str | None] = mapped_column(String(200), nullable=True)
    education_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    place_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ApplicantRow(Base):
    __tablename__ = "mai_applicant_rows"
    __table_args__ = (
        Index("ix_mai_rows_snapshot_application", "snapshot_id", "application_id"),
        Index("ix_mai_rows_snapshot_group", "snapshot_id", "group_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("mai_snapshots.id"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("mai_competition_groups.id"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)


class GroupStat(Base):
    __tablename__ = "mai_group_stats"
    __table_args__ = (UniqueConstraint("snapshot_id", "group_id", name="uq_mai_group_stat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("mai_snapshots.id"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("mai_competition_groups.id"), nullable=False, index=True)
    rows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_consent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ApplicantDailyMetric(Base):
    __tablename__ = "mai_applicant_daily_metrics"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "group_id", "application_id", name="uq_mai_daily_metric"),
        Index("ix_mai_metrics_snapshot_application", "snapshot_id", "application_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("mai_snapshots.id"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("mai_competition_groups.id"), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    real_competitor_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    above_with_consent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    above_without_consent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    general_gap_to_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent_gap_to_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    real_gap_to_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend_consent_above_3d: Mapped[float | None] = mapped_column(Float, nullable=True)


class SearchLog(Base):
    __tablename__ = "mai_search_logs"
    __table_args__ = (
        Index("ix_mai_search_logs_ip_created", "ip", "created_at"),
        Index("ix_mai_search_logs_application_created", "application_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, index=True)
    ip: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("mai_snapshots.id"), nullable=True)
    found: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    directions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
