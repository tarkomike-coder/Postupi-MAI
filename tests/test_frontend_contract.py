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
        "Каскад поступающих",
        "Состав конкуренции",
        "Динамика",
        "Прогноз проходного балла",
        "Не хватает мест",
        "по согласиям",
        "по каскаду",
    ]:
        assert expected in text

    assert "Chart" in text
    assert "charts-grid" in text


def test_frontend_copy_does_not_use_banned_terms():
    text = _public_text().lower()

    for banned in ["пока", "snapshot", "pipeline", "baseline", "successful snapshot"]:
        assert banned not in text
