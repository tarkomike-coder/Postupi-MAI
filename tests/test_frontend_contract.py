from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _public_text() -> str:
    return "\n".join(
        [
            (ROOT / "site" / "index.html").read_text(encoding="utf-8"),
            (ROOT / "site" / "app.js").read_text(encoding="utf-8"),
        ]
    )


def test_frontend_exposes_compact_analytics_dashboard():
    text = _public_text()

    for expected in [
        "Оценка шансов",
        "Реальные шансы",
        "По текущему каскаду",
        "Куда проходит",
        "Каскад поступающих",
        "Кто реально мешает",
        "Кто может добавиться",
        "Динамика",
        "Места в списках",
        "position-table",
        "Текущий расчёт",
        "по согласиям",
        "по каскаду",
        "если подтвердятся без согласия",
        "real-chance",
        "status-pass",
    ]:
        assert expected in text

    assert "Chart" in text
    assert "charts-grid" in text


def test_frontend_copy_does_not_use_banned_terms():
    text = _public_text().lower()

    for banned in ["пока", "snapshot", "pipeline", "baseline", "successful snapshot"]:
        assert banned not in text


def test_frontend_copy_avoids_confusing_admissions_terms():
    text = _public_text().lower()

    for banned in ["1422086", "напряжённый сценарий", "проходной по каскаду", "в зоне"]:
        assert banned not in text
