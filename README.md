# Postupi MAI

Публичный сервис `mai.tarko.su` для поиска номера заявления в очных бюджетных конкурсах МАИ по данным Госуслуг.

## Что Уже Есть

- FastAPI backend.
- PostgreSQL-ready модели через SQLAlchemy.
- Локальный SQLite fallback для разработки.
- Импорт Госуслуг `orgId=19`, 2026 год.
- Сжатое сохранение raw JSON вне git.
- Предрасчёт позиций, согласий и реальных конкурентов.
- `POST /api/search` без номера заявления в URL.
- Бессрочный журнал поисков в БД.
- Rate-limit без captcha.
- Статический frontend.
- nginx/systemd templates для VPS.

## Локальный Запуск

```powershell
python -m pip install -r backend\requirements.txt
python -m backend.worker import
python -m backend.worker import-bauman
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8013
```

Открыть:

```text
http://127.0.0.1:8013/
```

Если импорт Госуслуг недоступен, API и frontend всё равно запускаются, но поиск покажет, что данные загружаются.

## Тесты

```powershell
python -m pytest -q
```

## Яндекс.Метрика

В frontend нет жестко заданного счетчика. Для `mai.tarko.su` нужен отдельный счетчик без Вебвизора.

Подключение делается через глобальную переменную до `/app.js`:

```html
<script>window.MAI_METRIKA_ID = 12345678;</script>
<script src="/app.js"></script>
```

Номер заявления не передается в URL, параметры Метрики или цели.

## Публичный Репозиторий

Не коммитить:

- `.env`;
- production `DATABASE_URL`;
- дампы БД;
- raw JSON;
- production-логи;
- SSH-ключи;
- OAuth/API-токены;
- systemd environment files.

`.env.example` содержит только имена переменных.

## VPS

Ожидаемая схема:

- код: `/opt/postupi-mai`;
- frontend: `/var/www/mai-tarko`;
- backend: `127.0.0.1:8013`;
- база/роль PostgreSQL: `mai`;
- systemd: `mai-backend.service`, `mai-worker.service`, `mai-worker.timer`;
- Bauman systemd: `bauman-worker.service`, `bauman-worker.timer`;
- nginx: `deploy/nginx/mai-tarko.conf`.

Перед применением nginx-конфига проверить, что глобальная зона `perip` уже есть в `/etc/nginx/nginx.conf`, как в текущем `tarko-hub`.
