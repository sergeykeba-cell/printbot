# PrintBot Instance Manager

Оркестратор ізольованих Single-Tenant стеків для мережі точок печати.

## Архітектура

```
[Client] → [Traefik] → [Instance Stack N]
                              ├── FastAPI (api)
                              ├── Celery (worker)
                              ├── PostgreSQL (db)
                              └── Redis

[SuperAdmin] → [Manager API] → [ARQ Queue] → [ARQ Worker]
                    ↕                              ↕
              [Manager DB]              [Docker Compose CLI]
```

## Швидкий старт

```bash
# 1. Змінні оточення
cp .env.example .env
# Заповни MANAGER_API_KEY, ENCRYPTION_KEY, MANAGER_DATABASE_URL, REDIS_URL

# 2. Генерація ключів
python -c "import secrets; print(secrets.token_urlsafe(32))"  # MANAGER_API_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY

# 3. Міграції БД Менеджера
alembic upgrade head

# 4. Запуск Manager API
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 5. Запуск ARQ Worker (окремий процес)
arq app.worker.WorkerSettings
```

## API Ендпоінти

Всі запити вимагають заголовок: `X-API-Key: <MANAGER_API_KEY>`

| Метод | Шлях | Опис |
|-------|------|------|
| POST | `/api/instances/create` | Створити новий інстанс |
| GET | `/api/instances` | Список інстансів (без секретів) |
| GET | `/api/instances/{id}/logs` | Логи інстансу |
| POST | `/api/instances/{id}/retry` | Перезапустити провізіонінг |
| POST | `/api/instances/{id}/action` | stop / start / restart |
| DELETE | `/api/instances/{id}?confirm=true` | Видалити інстанс |

## Безпека — закриті вразливості

| # | Вразливість | Рішення |
|---|-------------|---------|
| 1 | RCE через субдомен (bash injection) | Regex `^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$` |
| 2 | Відсутня автентифікація API | X-API-Key на весь роутер |
| 3 | `docker ps grep` (хибні збіги) | `docker compose -p <project>` |
| 4 | Resource limits (Swarm-only deploy:) | `mem_limit` / `cpus` напряму |
| 5 | Реєстр інстансів відсутній | InstanceRegistry в PostgreSQL |
| 6 | Бекап без перевірки (порожній файл) | temp → mv + exit codes |
| 7 | db_password не зберігався | Fernet шифрування в реєстрі |
| 8 | Дефолтний API ключ в коді | `os.environ["KEY"]` (KeyError при старті) |
| 9 | Async/sync ORM змішування | AsyncSession скрізь + ARQ |
| 10 | tg_bot_token у відкритому вигляді | Fernet шифрування (обидва секрети) |
| 11 | .env права 644 (TOCTOU) | `os.open()` з `0o600` за один syscall |
| 12 | Deprecated `Query.get()` | `db.scalar(select(...).where(...))` |
| 13 | `onupdate` ненадійний | PostgreSQL тригер через Alembic |
| 14 | Блокуючий I/O в event loop | `asyncio.to_thread()` для всіх syscall |
| 15 | BackgroundTasks для важких задач | ARQ (окремий воркер-процес) |
| 16 | Немає механізму restart при crash | `/retry` ендпоінт + decrypt з реєстру |
| 17 | `server_onupdate` не генерує DDL | Alembic міграція з тригером |
| 18 | Секрети в Redis (ARQ args) | Воркер отримує тільки `instance_id` |
| 19 | Double retry race condition | Перевірка `status in (active, provisioning)` |
| 20 | Відсутня перевірка шаблону | `FileNotFoundError` до будь-яких змін |
| 21 | `WorkerSettings.redis_settings = ...` | `RedisSettings.from_dsn(os.environ["REDIS_URL"])` |
| 22 | `os.environ.get()` з дефолтом (регресія) | `os.environ["REDIS_URL"]` скрізь |
| 23 | Instance не перевіряється після деплою | Явна перевірка `if not instance: return` |
| 24 | `docker logs` без таймауту | `timeout=15` в subprocess.run |
| 25 | `/action` без Enum валідації | `InstanceAction(str, Enum)` в Pydantic |
| 26 | Тригер без explicit схеми | `public.update_updated_at_column()` |

## Структура файлів

```
printbot-manager/
├── manager_app/
│   ├── main.py          # FastAPI app entrypoint
│   ├── models.py        # SQLAlchemy 2.0 InstanceRegistry
│   ├── manager_db.py    # AsyncSession factory + Depends
│   ├── security.py      # API Key auth + Fernet encrypt/decrypt
│   ├── orchestrator.py  # REST API ендпоінти
│   └── worker.py        # ARQ воркер (окремий процес)
├── alembic/
│   └── versions/
│       └── 0001_add_updated_at_trigger.py
├── infrastructure/
│   ├── templates/
│   │   └── docker-compose.instance.yml  # Шаблон стеку інстансу
│   ├── update_all_instances.sh          # Rolling update
│   └── backup_instance.sh              # Резервна копія
├── requirements.txt
└── .env.example
```

## Запуск ARQ Worker

```bash
# Окремий процес, завжди запускати поруч з API
arq app.worker.WorkerSettings

# Або через supervisor/systemd для автозапуску
```

## Відповіді на архітектурні питання

**GET /logs — REST чи WebSocket?**
Поточна реалізація: REST з `--tail=100`. Для live-стріму логів — додати
WebSocket ендпоінт з `docker compose logs -f` через `asyncio.create_subprocess_exec`.

**`/action: stop` vs повне знесення?**
`stop` — зупиняє контейнери, volumes збережені.
`DELETE /instances/{id}?confirm=true` — видаляє запис з реєстру + `compose stop`.
Повне знесення з volumes (`compose down -v`) — навмисно тільки ручна операція.
