# STATUS: Postupi MAI

Обновлено: 2026-07-10, MSK.

`mai.tarko.su` - публичный сервис аналитики поступления в МАИ по номеру заявления. Источник данных для МАИ: Госуслуги, `orgId=19`, 2026 год. Старый проект `C:\Projects\Postupi` используется только как референс по логике и визуалу; его не трогаем.

## Где Что Лежит

- Код нового проекта: `C:\Projects\mai`.
- Инфраструктурная карта VPS и nginx: `C:\Projects\tarko-hub`.
- Старый Postupi: `C:\Projects\Postupi`.
- GitHub нового проекта: `tarkomike-coder/Postupi-MAI`.
- Продовый код на VPS: `/opt/postupi-mai`.
- Продовый frontend: `/var/www/mai-tarko`.
- Продовая БД: PostgreSQL, база `mai`.
- Backend: `mai-backend.service`, `127.0.0.1:8013`.
- MAI импорт: `mai-worker.timer`, каждый день в 09:10 MSK.
- Bauman импорт: `bauman-worker.timer`, каждый день в 09:30 MSK.

## Текущее Состояние Продакшена

Проверено 2026-07-09:

- `mai-backend.service`: active.
- `postgresql@16-main.service`: active.
- `/api/status`: отвечает, данные есть.
- `/api/ready`: отвечает `status=ok`.
- SQLite-файлов в `/opt/postupi-mai` нет.

### Фикс Поиска Кода Поступающего 2026-07-10

- Проверена жалоба "код поступающего не работает": свежий неудачный поиск был
  по номеру `7598838654`; такого `application_id` нет ни в текущих, ни в
  исторических срезах `mai`/`bauman`.
- Сразу после него тот же пользователь искал `1171228`, и поиск успешно вернул
  `5` направлений.
- Важно: "номер заявления" и "код/ID поступающего" - разные идентификаторы.
  В публичном JSON Госуслуг по конкурсным спискам есть поле `idApplication`;
  именно его мы храним как `application_id` и именно по нему ищем.
  В raw-срезе рядом с ним нет отдельного поля с 10-значным номером заявления,
  поэтому автоматически перевести `7598838654` в 7-значный ID поступающего
  нельзя.
- Backend теперь нормализует ввод кода поступающего до цифр, поэтому варианты
  вроде `№ 1 171 228` ищутся как `1171228`.
- Frontend переименован с "номер заявления" на "код поступающего / ID
  поступающего", очищает ввод до цифр перед отправкой и показывает более точный
  текст для `не найдено`.
- Обновлены `backend/api.py`, `backend/services/search.py`, `site/app.js`,
  `site/index.html`; cache-busting версии статики поднят до `20260710-2`.
- Проверка: `python -m pytest -q` -> `23 passed`.
- Продовая проверка:
  - `№ 1 171 228` -> `1171228`, `found=true`, `5` направлений;
  - `7598838654` -> `found=false`, потому что это не `idApplication` из
    публичных конкурсных списков.

### SEO И Справочный FAQ 2026-07-10

- На главную добавлен закрытый справочный блок `Как это работает` на `<details>`:
  пользователь видит только вопросы, ответы раскрываются по нажатию.
- Темы FAQ: что такое код поступающего, отличие от номера заявления, какие
  данные используются, что значит расчёт по каскаду.
- В `<head>` добавлены усиленные `title`, `description`, `canonical`, Open Graph,
  `WebApplication` и `FAQPage` JSON-LD.
- Созданы реальные `/robots.txt` и `/sitemap.xml`; раньше эти пути через nginx
  fallback отдавали главную HTML-страницу.
- CSS cache-busting поднят до `20260710-4`.
- Проверка: `python -m pytest -q` -> `24 passed`.
- Продовая проверка:
  - `/robots.txt` отдаёт `Sitemap: https://mai.tarko.su/sitemap.xml`;
  - `/sitemap.xml` отдаёт XML с `https://mai.tarko.su/`;
  - в HTML есть `4` закрытых FAQ-пункта и `FAQPage`.

Текущие данные в PostgreSQL:

| Таблица | Строк |
|---|---:|
| `mai_snapshots` | 1 |
| `mai_competition_groups` | 49 |
| `mai_applicant_rows` | 44 945 |
| `mai_applicant_daily_metrics` | 41 084 |
| `mai_search_logs` | 23 |
| `bauman_snapshots` | 1 |
| `bauman_competition_groups` | 41 |
| `bauman_applicant_rows` | 38 462 |

Последний набор данных МАИ:

- id: `1`;
- status: `ok`;
- групп: `49`;
- строк заявлений: `44 945`;
- уникальных номеров заявлений: `11 810`;
- finished_at: `2026-07-09 10:39:28 UTC`.

Последний набор данных Бауманки:

- id: `1`;
- status: `ok`;
- групп: `41`;
- строк заявлений: `38 462`;
- уникальных номеров заявлений: `10 776`;
- finished_at: `2026-07-09 11:30:37 UTC`.

## Что Уже Сделано

- Создан отдельный проект `mai.tarko.su` на FastAPI + статический frontend.
- Развернут backend на VPS через systemd.
- Развернут frontend через nginx.
- Подключен PostgreSQL на VPS.
- Настроен ежедневный сбор МАИ из Госуслуг.
- Настроен ежедневный сбор Бауманки из Госуслуг для будущей аналитики.
- Реализован поиск по номеру заявления через `POST /api/search`.
- Реализован бессрочный журнал поисков: время, IP, user-agent, введенный номер, найдено/не найдено, число направлений, rate-limit, время ответа, код ошибки.
- Реализован rate-limit без captcha: при частых запросах поиск временно ограничивается.
- Убран локальный SQLite fallback: без `DATABASE_URL` приложение не стартует и не создает левую БД.
- Удален локальный файл `backend/mai_local.db`.
- Подключена Яндекс.Метрика `110548873` с Webvisor.
- Добавлен `noscript`-пиксель Метрики.
- Номер заявления не передается в URL страницы.
- Номер заявления не передается в параметры целей Метрики.

## Возможности Интерфейса

Главный сценарий:

1. Пользователь вводит номер заявления.
2. Сервис ищет его в последнем наборе данных МАИ.
3. Если номер найден, показывает все направления МАИ, куда подано заявление.

Показывается:

- общий статус заявления;
- куда проходит по текущему расчету с учетом приоритетов;
- реальные шансы, выделенные зеленым;
- направления, приоритеты и бюджетные места;
- место в общем списке;
- место среди тех, кто уже подал согласие;
- место по каскаду;
- текущий расчет: проходит или сколько мест должно освободиться;
- люди выше, которые реально мешают;
- люди выше, которые уходят по каскаду;
- люди выше без согласия;
- сценарные проценты;
- графики и таблица по найденным направлениям.

Графики/отчеты на странице:

- кто реально мешает;
- кто может добавиться без согласия;
- места в списках;
- оценка шансов по сценариям;
- история по дням, когда появится больше дневных наборов данных.

Текст внизу:

- `Это аналитика по текущим данным Госуслуг`.

## Как Сейчас Считается Аналитика

База расчета:

- берется последний дневной набор данных МАИ;
- для каждого номера заявления собираются все направления;
- учитываются балл, место, приоритет, согласие и число бюджетных мест;
- строится каскад по всем поступающим, у кого есть согласие;
- человек считается реальным конкурентом направления, если общий расчет приоритетов ведет его именно туда.

Текущий прогноз:

- не является полноценным Monte Carlo из старого `Postupi`;
- использует детерминированный каскад и сценарные проценты;
- отдельно показывает направление, куда заявление проходит по текущему каскаду;
- если не проходит никуда, показывает ближайшее направление и сколько мест нужно.

Важно: полноценный Monte Carlo из `C:\Projects\Postupi` еще не перенесен в новый `mai`. Старый код содержит более сложную модель: deferred acceptance + Monte Carlo по поведению согласий. Его нужно переносить отдельной задачей после согласования.

## API

Публичные endpoint'ы:

- `GET /api/health` - простая проверка backend.
- `GET /api/ready` - проверка backend + наличие данных.
- `GET /api/status` - статус последнего набора данных.
- `POST /api/search` - поиск заявления.

Формат поиска:

```json
{"application_id": "1234567"}
```

Ручного публичного admin endpoint для обновления данных в текущей версии нет. Ручной запуск возможен через worker на сервере:

```bash
cd /opt/postupi-mai
sudo -u mai -E /opt/postupi-mai/backend/.venv/bin/python -m backend.worker import
sudo -u mai -E /opt/postupi-mai/backend/.venv/bin/python -m backend.worker import-bauman
```

Если нужен ручной web/admin-запуск, это отдельная задача: endpoint с `MAI_ADMIN_TOKEN`, без публикации токена в репозитории.

## Отчеты Из БД

Количество данных:

```bash
sudo -u postgres psql -d mai -P pager=off -F $'\t' -At <<'SQL'
select 'mai_snapshots', count(*) from mai_snapshots;
select 'mai_competition_groups', count(*) from mai_competition_groups;
select 'mai_applicant_rows', count(*) from mai_applicant_rows;
select 'mai_applicant_daily_metrics', count(*) from mai_applicant_daily_metrics;
select 'mai_search_logs', count(*) from mai_search_logs;
select 'bauman_snapshots', count(*) from bauman_snapshots;
select 'bauman_competition_groups', count(*) from bauman_competition_groups;
select 'bauman_applicant_rows', count(*) from bauman_applicant_rows;
SQL
```

Поиски за сегодня:

```bash
sudo -u postgres psql -d mai -P pager=off -F $'\t' -At <<'SQL'
select
  to_char(created_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD HH24:MI:SS'),
  ip,
  application_id,
  found,
  directions_count,
  rate_limited
from mai_search_logs
where (created_at AT TIME ZONE 'Europe/Moscow')::date = current_date
order by created_at desc;
SQL
```

Последние поиски:

```bash
sudo -u postgres psql -d mai -P pager=off -F $'\t' -At <<'SQL'
select
  to_char(created_at AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD HH24:MI:SS'),
  ip,
  application_id,
  found,
  directions_count,
  rate_limited,
  response_ms
from mai_search_logs
order by created_at desc
limit 50;
SQL
```

## Яндекс.Метрика

Подключен счетчик:

- id: `110548873`;
- Webvisor: включен;
- clickmap: включен;
- trackLinks: включен;
- accurateTrackBounce: включен;
- noscript-пиксель: добавлен.

Frontend также отправляет цели:

- `search_submitted`;
- `search_found`;
- `search_not_found`;
- `rate_limited`.

В цели не передается номер заявления.

## Безопасность И Секреты

Что сделано:

- `.env`, `.env.*`, дампы БД, SQLite-файлы, raw JSON и логи исключены через `.gitignore`.
- `.env.example` содержит только имена переменных без значений.
- Продовый env лежит на VPS: `/opt/postupi-mai/backend/.env`, права `600`.
- `DATABASE_URL` и `MAI_ADMIN_TOKEN` не опубликованы.
- SQLite fallback удален из кода.
- Локальная `backend/mai_local.db` удалена.
- На VPS SQLite-файлов в `/opt/postupi-mai` не найдено.
- Яндекс counter id `110548873` не является секретом.

Проверка секретов выполнялась командой:

```powershell
rg -n -i "password|passwd|secret|token|DATABASE_URL=|postgresql://|postgres://|MAI_ADMIN_TOKEN|BEGIN .*PRIVATE KEY|api[_-]?key|oauth|bearer|ssh-rsa|ed25519" -S --glob '!backend/mai_local.db' --glob '!data/raw/**' --glob '!.git/**' .
```

Найдено только:

- имена переменных в `.env.example`;
- упоминание `MAI_ADMIN_TOKEN` в `backend/config.py`;
- пункты плана в `docs/superpowers/...`.

Значений секретов в репозитории не найдено.

## Проверки

Локальные тесты:

```text
20 passed in 1.03s
```

Продовые проверки:

```text
GET https://mai.tarko.su/api/ready -> status=ok
GET https://mai.tarko.su/api/status -> has_data=true
mai-backend.service -> active
postgresql@16-main.service -> active
```

Проверка Метрики:

- `index.html` содержит `window.MAI_METRIKA_ID = 110548873`;
- `index.html` содержит `mc.yandex.ru/watch/110548873`;
- `app.js` содержит загрузку `mc.yandex.ru/metrika/tag.js?id=...`;
- `app.js` содержит `webvisor: true`.

## Нерешенные Вопросы

1. Переносить ли полноценный Monte Carlo из старого `Postupi` в новый `mai`.
2. Делать ли публичный/закрытый админ-эндпоинт для ручного обновления.
3. Делать ли интерфейс по Бауманке или оставить Бауманку только как сохранение данных.
4. Добавлять ли нормальные миграции вместо `Base.metadata.create_all`.
5. Нужна ли отдельная админ-страница с поисковыми логами.
6. Нужны ли отдельные nginx access logs/дашборд именно для `mai.tarko.su` сверх уже существующих логов и Метрики.

## Текущий Git-Статус

Последний опубликованный коммит:

```text
6da24ed Build MAI admissions analytics dashboard
```

Он запушен в `origin/main` (`tarkomike-coder/Postupi-MAI`).

Локально может оставаться неотслеживаемая папка `artifacts/`.
Это рабочая папка для временных превью, скриншотов и проверочных артефактов во время разработки.
Она не является исходником продукта, не нужна для деплоя и намеренно не добавляется в Git.
