# mai.tarko.su Admissions Analytics Design

## Summary

`mai.tarko.su` is a public admissions analytics service for MAI. A visitor enters an application number, and the site shows all full-time budget MAI competition groups from Gosuslugi where that number appears, with facts, history, and scenario-based guidance.

The only data source for MVP is the public Gosuslugi API for `orgId=19` MAI. The service must not use `priem.mai.ru` or manual parsers in MVP.

The production target is the existing Tarko VPS with nginx, systemd, and PostgreSQL. The GitHub repository is public, so code and docs must not include environment secrets, database dumps, raw snapshots, private logs, or production credentials.

## Architecture

Use the reliable MVP architecture discussed as option B.

- nginx serves a static frontend for `mai.tarko.su`.
- nginx proxies `/api/` to a separate FastAPI service on localhost, expected port `8013`.
- PostgreSQL has a separate `mai` database and role.
- A separate systemd worker/timer performs daily data collection and metric computation.
- The public API only reads already stored data. It never calls Gosuslugi and never runs heavy cascade or scenario calculations during a visitor request.
- Manual refresh creates a background job and returns quickly with job status information.

This keeps the user path fast even if Gosuslugi is slow or unavailable.

## Data Collection

The worker stores one complete daily MAI dataset.

Pipeline:

1. Fetch MAI competition groups from Gosuslugi `orgId=19`.
2. Select full-time budget competition groups.
3. Fetch applicants for each selected group.
4. Store compressed raw JSON outside git.
5. Normalize rows into PostgreSQL.
6. Compute group statistics.
7. Compute the current cascade/deferred-acceptance baseline.
8. Compute fixed scenario metrics.
9. Store applicant daily metrics for fast lookup.
10. Mark the data update as successful or failed.

The public search reads the latest usable data from PostgreSQL and should complete in tens or hundreds of milliseconds under normal conditions.

## Storage

Core tables:

- `mai_snapshots`: one daily data update, timestamps, status, duration, group count, row count, unique application count, error text.
- `mai_competition_groups`: Gosuslugi group id, OKSO, name, level, form, place type, budget seats.
- `mai_applicant_rows`: snapshot, group, application number, position, score, priority, consent, category.
- `mai_group_stats`: per-group daily aggregates.
- `mai_applicant_daily_metrics`: precomputed facts and scenario metrics for fast dashboard responses.
- `mai_search_logs`: permanent search log with timestamp, IP, user agent, application number, snapshot id, found flag, direction count, rate-limit flag, response time, and error code.

Search logs are retained indefinitely. They are for administration, diagnostics, abuse control, and understanding usage. They must not be committed or exposed publicly.

## Public API

Use `POST /api/search` with a JSON body instead of query parameters, so application numbers do not appear in URLs, browser history, referrers, or nginx access-log request lines.

Expected public endpoints:

- `GET /api/health`: process health for monitoring.
- `GET /api/ready`: backend, database, and data freshness check for monitoring.
- `GET /api/status`: public data freshness/status summary.
- `POST /api/search`: search by application number.

Admin endpoints can exist for refresh/status, but they must be protected. MVP admin log inspection can be done over SSH/SQL instead of building a public admin UI.

## Rate Limiting

Do not use captcha in MVP.

Use a local rate limit:

- nginx `limit_req` on `/api/search`.
- backend limit using `mai_search_logs`.
- limit both total searches and distinct application numbers per IP in a time window.
- when exceeded, return HTTP `429` with `retry_after_seconds`.

User-facing message:

`Слишком много запросов подряд. Поиск временно ограничен, попробуйте позже.`

## User Interface

The interface must avoid internal technical terms. Do not show words like snapshot, job, ready, pipeline, baseline, metrics, or successful snapshot. Also avoid the word `пока` in public UI copy.

Allowed user-facing status examples:

- `Данные обновлены: 9 июля, 09:12`
- `Идёт обновление. Показываем данные от 9 июля, 09:12.`
- `Данные загружаются. Попробуйте позже.`
- `Номер заявления не найден в очных бюджетных конкурсах МАИ.`
- `Слишком много запросов подряд. Поиск временно ограничен, попробуйте позже.`
- `Прогноз основан на текущих списках и сценариях поведения абитуриентов. Это не официальный результат зачисления.`

Main MVP screen:

- application number input;
- search button;
- result cards for every MAI direction where the number appears;
- facts from the latest data update;
- history by day;
- scenario explanation without magic percentages;
- simple empty/error/rate-limit states.

## Forecasting

Do not present Monte Carlo as a precise admission probability in MVP.

Show:

- current facts;
- position in the full list;
- position among applicants with consent;
- position among realistic competitors based on current priorities and cascade;
- budget seats;
- score;
- competitors above with and without consent;
- daily trends;
- scenario labels and explanations.

Fixed scenarios are precomputed after each data update. The visitor page does not recalculate scenarios interactively.

## Monitoring And Operations

Operational checks are for the administrator, not for the public UI.

Required operational pieces:

- separate nginx logs for `mai.tarko.su`;
- request timing and upstream timing in access logs;
- `health` and `ready` endpoints;
- add `mai-web`, `mai-api-health`, and `mai-api-ready` checks to the existing Tarko monitoring;
- systemd service for FastAPI;
- systemd service/timer for the daily worker;
- manual refresh command or protected endpoint.

Public visitors only see simple data freshness and availability messages.

## Analytics

Add Yandex Metrika with a separate counter for `mai.tarko.su`.

Rules:

- do not reuse the `alexander.tarko.su` counter;
- do not send application numbers to Metrika;
- do not put application numbers in page URLs;
- do not enable Webvisor for MVP;
- safe goals: search submitted, found, not found, rate limited.

If Yandex Webmaster is needed, add `robots.txt`, `sitemap.xml`, and the verification HTML file through the deployment/build process, not by hand-editing generated output.

## Security And Public Repository Hygiene

The repository is public.

Never commit:

- `.env` files;
- database URLs or passwords;
- PostgreSQL dumps;
- raw Gosuslugi JSON snapshots;
- production logs;
- SSH keys;
- OAuth/API tokens;
- production systemd environment files.

Application numbers from public lists are not treated as personal secrets, but search logs that combine application number, IP, user agent, and timestamp are operational records and stay only in PostgreSQL/server logs.

Tests must use synthetic application numbers.

## Open Decisions

- Exact daily schedule time.
- Exact nginx/backend rate-limit thresholds.
- Whether admin refresh is CLI-only for MVP or also a protected HTTP endpoint.
- Exact Yandex Metrika counter id for `mai.tarko.su`.
