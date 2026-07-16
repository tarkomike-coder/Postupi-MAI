from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _public_text() -> str:
    return "\n".join(
        [
            (ROOT / "site" / "index.html").read_text(encoding="utf-8"),
            (ROOT / "site" / "app.js").read_text(encoding="utf-8"),
            (ROOT / "site" / "styles.css").read_text(encoding="utf-8"),
        ]
    )


def test_frontend_exposes_compact_analytics_dashboard():
    text = _public_text()

    for expected in [
        "МАИ 2026: поступление, списки поступающих, конкурсные списки, проходные баллы, бюджет, калькулятор шансов по коду",
        "Списки поступающих МАИ 2026, бюджет и шансы по коду",
        "калькулятор шансов на поступление",
        "проходные баллы",
        "текущую оценку шансов на бюджет",
        "Код поступающего / ID поступающего",
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
        "https://t.me/MikRUS777",
        "https://max.ru/u/f9LHodD0cOIc93Y0M9eCBRVmxWS4Nin-yIZHWERwhlV2euQ9RE608IHwUn8",
        "contact-footer",
        "Как это работает",
        '<details class="faq-block">',
        "Что такое код поступающего?",
        "Чем код поступающего отличается от номера заявления?",
        "Какие данные используются?",
        "Как оценить шансы поступления в МАИ?",
        "Можно ли узнать вероятность поступления в МАИ?",
        "проверить шансы поступления на бюджет",
        "даёт не точную вероятность поступления в процентах",
        "application/ld+json",
        "FAQPage",
        "WebApplication",
        "homepage-overview",
        "МАИ 2026: текущая картина по конкурсным спискам",
        "Данные рассчитаны только по публичным конкурсным спискам Госуслуг.",
        "Все направления: места, заявления, согласия и расчетный балл",
        "Один поступающий может быть в нескольких конкурсных списках",
        "Заявлений в списке",
        "Расчетный балл на бюджет",
        "Конкурс, чел./место",
        "Что значит учет приоритетов?",
        "Как читать таблицу",
        "не официальный проходной балл",
        "Балл может быть выше 300",
        "индивидуальные достижения",
        "Направления с наибольшей конкурсной нагрузкой",
        "/api/overview",
        "data-open-faq",
        'id="faq-cascade"',
        "/api/directions/",
        "directionPageId",
        "direction-chart-grid",
        "Расчетный список с учетом согласий и приоритетов",
        "В списке находятся поступающие с согласием",
        "Если поступающий проходит на направление с более высоким приоритетом",
        "Расчетный балл на бюджет",
        "Заявлений в списке",
        "Конкурс, человек на место",
        "direction-applicant-table",
        "Код поступающего",
        "Расчетный список по направлению не сформирован.",
        "loading-panel",
        "spinner",
        "Получаем расчетные данные по направлениям.",
        "direction-link",
        "text-decoration: underline",
        "direction_open",
        "direction_click",
        "reachGoal",
    ]:
        assert expected in text

    assert "Chart" in text
    assert "charts-grid" in text
    assert 'rel="canonical"' not in text


def test_frontend_copy_does_not_use_banned_terms():
    text = _public_text().lower()

    for banned in [
        "пока",
        "snapshot",
        "pipeline",
        "baseline",
        "successful snapshot",
        "уплотнил",
        "уплотнились",
        "рыхл",
        "мусор",
        "исходные данные",
    ]:
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


def test_search_engine_entry_files():
    robots = (ROOT / "site" / "robots.txt").read_text(encoding="utf-8")
    sitemap = (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8")

    assert "Sitemap: https://mai.tarko.su/sitemap.xml" in robots
    assert "<loc>https://mai.tarko.su/</loc>" in sitemap
    assert "<loc>https://mai.tarko.su/directions/33546</loc>" in sitemap
    assert "<loc>https://mai.tarko.su/directions/117502</loc>" in sitemap
    assert "<loc>https://mai.tarko.su/directions/146637</loc>" in sitemap
    assert "<urlset" in sitemap
    assert sitemap.count("<url>") == 50


def test_frontend_copy_avoids_confusing_admissions_terms():
    text = _public_text().lower()

    for banned in ["1422086", "напряжённый сценарий", "проходной по каскаду", "в зоне"]:
        assert banned not in text
