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
        "Аналитика поступления по номеру заявления",
        "Главный вывод по текущим данным",
        "Куда проходит заявление",
        "Оценка устойчивости",
        "Почему проходит",
        "Что может изменить ситуацию",
        "Каскад поступающих",
        "Кто реально мешает",
        "Кто может добавить риск",
        "Сравнение направлений",
        "Места в списках",
        "место в общем списке",
        "место среди согласий",
        "место по каскаду",
        "резерв: проходит",
        "если станет первым",
        "position-table",
        "Текущий расчёт",
        "по согласиям",
        "по каскаду",
        "real-chance",
        "status-pass",
        "status-reserve-pass",
    ]:
        assert expected in text

    assert "Chart" in text
    assert "charts-grid" in text


def test_frontend_copy_does_not_use_banned_terms():
    text = _public_text().lower()

    for banned in ["пока", "snapshot", "pipeline", "baseline", "successful snapshot"]:
        assert banned not in text


def test_frontend_connects_yandex_metrika_counter():
    text = _public_text()

    assert "window.MAI_METRIKA_ID = 110548873" in text
    assert "mc.yandex.ru/metrika/tag.js" in text
    assert "mc.yandex.ru/watch/110548873" in text
    assert "webvisor: true" in text


def test_yandex_webmaster_verification_file():
    text = (ROOT / "site" / "yandex_3373b3a388de174b.html").read_text(encoding="utf-8")

    assert "Verification: 3373b3a388de174b" in text
    assert "charset=UTF-8" in text


def test_frontend_copy_avoids_confusing_admissions_terms():
    text = _public_text().lower()

    for banned in ["1422086", "напряжённый сценарий", "проходной по каскаду", "в зоне"]:
        assert banned not in text
