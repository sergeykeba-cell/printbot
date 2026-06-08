# PrintBot Instance Manager — Інструкція з розгортання та експлуатації

---

## Зміст

1. [Вимоги до сервера](#1-вимоги-до-сервера)
2. [Підготовка інфраструктури](#2-підготовка-інфраструктури)
3. [Розгортання Manager](#3-розгортання-manager)
4. [Генерація секретів та налаштування .env](#4-генерація-секретів-та-налаштування-env)
5. [Міграції бази даних](#5-міграції-бази-даних)
6. [Запуск сервісів](#6-запуск-сервісів)
7. [Перевірка що все працює](#7-перевірка-що-все-працює)
8. [Робота з API — практичні приклади](#8-робота-з-api--практичні-приклади)
9. [Створення нової точки печати](#9-створення-нової-точки-печати)
10. [Оновлення всіх інстансів](#10-оновлення-всіх-інстансів)
11. [Резервне копіювання](#11-резервне-копіювання)
12. [Автозапуск через systemd](#12-автозапуск-через-systemd)
13. [Типові помилки і їх усунення](#13-типові-помилки-і-їх-усунення)
14. [Структура директорій на сервері](#14-структура-директорій-на-сервері)

---

## 1. Вимоги до сервера

| Компонент | Мінімум | Рекомендовано |
|-----------|---------|---------------|
| ОС | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Диск | 40 GB SSD | 80 GB SSD |
| Docker | 24.x+ | latest |
| Docker Compose | v2.x+ (plugin) | latest |
| Python | 3.11+ | 3.12 |
| PostgreSQL | 15+ | 16 |
| Redis | 7.x | 7.x |

**Перевірити версії після встановлення:**
```bash
docker --version
docker compose version    # Має бути v2.x, не v1 (docker-compose)
python3 --version
psql --version
redis-cli --version
```

---

## 2. Підготовка інфраструктури

### 2.1 Встановлення Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

### 2.2 Створення Docker мережі (глобальна, для Traefik)

```bash
docker network create web_network
```

### 2.3 Запуск Traefik (глобальний reverse proxy)

```bash
mkdir -p /opt/printbot/infrastructure
```

Скопіюй файл `docker-compose.traefik.yml` на сервер і запусти:

```bash
docker compose -f /opt/printbot/infrastructure/docker-compose.traefik.yml up -d
```

Переконайся що Traefik запустився:
```bash
docker ps | grep traefik
# Має показати: global_traefik ... Up
```

### 2.4 Створення директорій

```bash
mkdir -p /opt/printbot/instances
mkdir -p /opt/printbot/backups
mkdir -p /opt/printbot/infrastructure/templates
```

### 2.5 Копіювання шаблону

```bash
cp docker-compose.instance.yml /opt/printbot/infrastructure/templates/
```

### 2.6 Встановлення Python-залежностей

```bash
cd /opt/printbot/manager
pip install -r requirements.txt
```

---

## 3. Розгортання Manager

### Структура на сервері після розгортання:

```
/opt/printbot/
├── manager/                     ← Код Manager API
│   ├── manager_app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── manager_db.py
│   │   ├── security.py
│   │   ├── orchestrator.py
│   │   └── worker.py
│   ├── alembic/
│   │   ├── alembic.ini
│   │   └── versions/
│   │       └── 0001_add_updated_at_trigger.py
│   ├── requirements.txt
│   └── .env                     ← НЕ в git, створюється вручну
├── infrastructure/
│   ├── templates/
│   │   └── docker-compose.instance.yml
│   ├── update_all_instances.sh
│   └── backup_instance.sh
├── instances/                   ← Тут оркестратор створює папки інстансів
│   ├── odessa-center/
│   │   ├── .env                 ← права 600, генерується автоматично
│   │   └── docker-compose.yml
│   └── kyiv-podil/
│       ├── .env
│       └── docker-compose.yml
└── backups/                     ← Резервні копії
    └── odessa-center/
        ├── db_20240115_120000.sql
        └── config_20240115_120000.tar.gz
```

### Ініціалізація Alembic (якщо вперше):

```bash
cd /opt/printbot/manager
alembic init alembic
```

У файлі `alembic/env.py` додай:
```python
from app.models import Base
target_metadata = Base.metadata
```

У файлі `alembic.ini` встанови:
```ini
sqlalchemy.url = postgresql+asyncpg://...  # або через env
```

---

## 4. Генерація секретів та налаштування .env

### 4.1 Генерація MANAGER_API_KEY

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Зберегти результат — це ключ доступу до Manager API.

### 4.2 Генерація ENCRYPTION_KEY

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

⚠️ **КРИТИЧНО:**
- Зберігати ключ окремо від бази даних (наприклад, у менеджері паролів або Vault)
- При втраті ключа — всі зашифровані секрети в БД стають нечитабельними
- Не ротувати ключ без попереднього дешифрування і перешифрування всіх записів

### 4.3 Заповнення .env

```bash
cp /opt/printbot/manager/.env.example /opt/printbot/manager/.env
chmod 600 /opt/printbot/manager/.env   # Права тільки для власника
nano /opt/printbot/manager/.env
```

Файл після заповнення:
```env
MANAGER_API_KEY=<результат з 4.1>
ENCRYPTION_KEY=<результат з 4.2>
MANAGER_DATABASE_URL=postgresql+asyncpg://manager_user:ПАРОЛЬ@localhost:5432/manager_db
REDIS_URL=redis://localhost:6379/0
ENV=production
```

### 4.4 Створення бази даних Менеджера

```bash
sudo -u postgres psql
```

```sql
CREATE USER manager_user WITH PASSWORD 'ПАРОЛЬ';
CREATE DATABASE manager_db OWNER manager_user;
\q
```

---

## 5. Міграції бази даних

```bash
cd /opt/printbot/manager
source .env  # або: export $(cat .env | xargs)

alembic upgrade head
```

Очікуваний результат:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, add_updated_at_trigger
```

Перевірити що тригер створився:
```bash
psql -U manager_user -d manager_db -c "\df public.update_updated_at_column"
# Має показати функцію тригера
```

---

## 6. Запуск сервісів

### 6.1 Manager API (FastAPI)

```bash
cd /opt/printbot/manager
uvicorn app.main:app --host 127.0.0.1 --port 8080 --workers 2
```

В продакшені порт 8080 не відкривати назовні — Traefik або Nginx проксіює.

### 6.2 ARQ Worker (окремий термінал або процес)

```bash
cd /opt/printbot/manager
arq app.worker.WorkerSettings
```

Очікуваний вивід при старті:
```
14:23:01: Starting worker for 1 functions: deploy_instance
14:23:01: redis_version=7.2.3 mem_usage=1.00M clients_connected=1
```

⚠️ **ARQ Worker і Manager API — два окремих процеси.** Обидва мають бути запущені одночасно.

---

## 7. Перевірка що все працює

### Health check:

```bash
curl http://localhost:8080/health
# {"status":"ok"}
```

### Перевірка автентифікації:

```bash
# Без ключа — має повернути 403
curl http://localhost:8080/api/instances
# {"detail":"Not authenticated"}

# З ключем — має повернути порожній список
curl -H "X-API-Key: ВАШ_MANAGER_API_KEY" http://localhost:8080/api/instances
# []
```

### Перевірка Redis (для ARQ):

```bash
redis-cli ping
# PONG
```

---

## 8. Робота з API — практичні приклади

У всіх запитах обов'язковий заголовок:
```
X-API-Key: ВАШ_MANAGER_API_KEY
```

### Отримати список всіх інстансів:

```bash
curl -H "X-API-Key: KEY" \
  http://localhost:8080/api/instances
```

З фільтром за статусом:
```bash
curl -H "X-API-Key: KEY" \
  "http://localhost:8080/api/instances?status_filter=active"
```

Статуси: `provisioning` | `active` | `failed` | `stopped`

### Переглянути логи інстансу:

```bash
curl -H "X-API-Key: KEY" \
  http://localhost:8080/api/instances/INSTANCE_ID/logs

# Або з кастомною кількістю рядків:
curl -H "X-API-Key: KEY" \
  "http://localhost:8080/api/instances/INSTANCE_ID/logs?tail=200"
```

Якщо статус `failed` — повертає `error_log` з бази (traceback деплою).
Якщо статус `active` — виконує `docker compose logs --tail=N` і повертає живі логи.

### Зупинити інстанс:

```bash
curl -X POST \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "stop"}' \
  http://localhost:8080/api/instances/INSTANCE_ID/action
```

### Запустити зупинений інстанс:

```bash
curl -X POST \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{"action": "start"}' \
  http://localhost:8080/api/instances/INSTANCE_ID/action
```

### Дозволені значення action: `stop`, `start`, `restart`

Будь-що інше (`down`, `down --volumes` тощо) — Pydantic поверне 422.

### Перезапустити провізіонінг (якщо деплой впав):

```bash
curl -X POST \
  -H "X-API-Key: KEY" \
  http://localhost:8080/api/instances/INSTANCE_ID/retry
```

Можливо тільки зі статусу `failed`. Зі статусу `active` або `provisioning` — 400.

### Видалити інстанс:

```bash
# Обов'язковий параметр confirm=true
curl -X DELETE \
  -H "X-API-Key: KEY" \
  "http://localhost:8080/api/instances/INSTANCE_ID?confirm=true"
```

Зупиняє контейнери. **Volumes (дані БД) НЕ видаляються** — залишаються на диску.
Для повного знесення з даними — вручну:
```bash
docker compose -p printbot_SUBDOMAIN down -v
```

---

## 9. Створення нової точки печати

```bash
curl -X POST \
  -H "X-API-Key: KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "subdomain": "odessa-center",
    "tg_bot_token": "1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }' \
  http://localhost:8080/api/instances/create
```

Вимоги до `subdomain`:
- Тільки малі латинські літери, цифри, дефіс
- Не починається і не закінчується на дефіс
- Довжина 3–63 символи
- Приклади: `odessa-center`, `kyiv-podil`, `lviv01`

Відповідь:
```json
{
  "status": "accepted",
  "instance_id": "uuid-тут",
  "url": "https://odessa-center.printbot.app"
}
```

Після цього ARQ Worker автоматично:
1. Читає секрети з БД і дешифрує
2. Створює `/opt/printbot/instances/odessa-center/.env` (права 600)
3. Копіює шаблон docker-compose
4. Виконує `docker compose up -d`
5. Оновлює статус → `active` (або `failed` з traceback)

Перевірити статус через 1-2 хвилини:
```bash
curl -H "X-API-Key: KEY" \
  http://localhost:8080/api/instances | python3 -m json.tool
```

---

## 10. Оновлення всіх інстансів

Після релізу нової версії `printbot-backend:latest`:

```bash
chmod +x /opt/printbot/infrastructure/update_all_instances.sh
/opt/printbot/infrastructure/update_all_instances.sh
```

Скрипт:
1. Підтягує новий образ `docker pull printbot-backend:latest`
2. Перезапускає кожен інстанс з новим образом
3. Запускає `alembic upgrade head` всередині кожного API контейнера
4. Збирає список невдалих оновлень і повертає exit code 1 якщо є помилки

При помилці в одному інстансі — скрипт продовжує решту і виводить список проблемних в кінці.

---

## 11. Резервне копіювання

```bash
chmod +x /opt/printbot/infrastructure/backup_instance.sh

# Бекап конкретного інстансу:
/opt/printbot/infrastructure/backup_instance.sh odessa-center
```

Результат у `/opt/printbot/backups/odessa-center/`:
```
db_20240115_120000.sql          ← pg_dump дамп бази
config_20240115_120000.tar.gz   ← docker-compose.yml (без .env — секрети виключені)
```

### Автоматичний щоденний бекап (cron):

```bash
crontab -e
```

Додати:
```cron
0 3 * * * /opt/printbot/infrastructure/backup_instance.sh odessa-center >> /var/log/printbot-backup.log 2>&1
```

### Відновлення з бекапу:

```bash
# 1. Знайти потрібний дамп
ls /opt/printbot/backups/odessa-center/

# 2. Відновити БД (контейнер має бути запущений)
cat /opt/printbot/backups/odessa-center/db_20240115_120000.sql | \
  docker compose -p printbot_odessa-center exec -T db \
  psql -U print_user print_instance_db
```

---

## 12. Автозапуск через systemd

### Manager API:

```bash
nano /etc/systemd/system/printbot-manager.service
```

```ini
[Unit]
Description=PrintBot Instance Manager API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/printbot/manager
EnvironmentFile=/opt/printbot/manager/.env
ExecStart=/usr/local/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### ARQ Worker:

```bash
nano /etc/systemd/system/printbot-worker.service
```

```ini
[Unit]
Description=PrintBot ARQ Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/printbot/manager
EnvironmentFile=/opt/printbot/manager/.env
ExecStart=/usr/local/bin/arq app.worker.WorkerSettings
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Активація:

```bash
systemctl daemon-reload
systemctl enable printbot-manager printbot-worker
systemctl start printbot-manager printbot-worker

# Перевірка:
systemctl status printbot-manager
systemctl status printbot-worker
```

---

## 13. Типові помилки і їх усунення

### Manager API не стартує — `KeyError: 'MANAGER_API_KEY'`

```
KeyError: 'MANAGER_API_KEY'
```

Змінні оточення не завантажені. Перевір:
```bash
echo $MANAGER_API_KEY   # Має бути не порожнім
cat /opt/printbot/manager/.env   # Файл існує і заповнений
```

При запуску через systemd — перевір `EnvironmentFile=` в unit файлі.

---

### Інстанс застряг у статусі `provisioning`

Причина: ARQ Worker не запущений або впав.

```bash
systemctl status printbot-worker
journalctl -u printbot-worker -n 50
```

Якщо Worker працює але інстанс все одно `provisioning` > 5 хвилин — подивись логи Worker:
```bash
journalctl -u printbot-worker -f
```

Після усунення причини — retry через API:
```bash
curl -X POST -H "X-API-Key: KEY" \
  http://localhost:8080/api/instances/INSTANCE_ID/retry
```

---

### Деплой впав — статус `failed`

Подивись traceback:
```bash
curl -H "X-API-Key: KEY" \
  http://localhost:8080/api/instances/INSTANCE_ID/logs
```

Типові причини:
- `FileNotFoundError: шаблон не знайдено` → перевір `/opt/printbot/infrastructure/templates/docker-compose.instance.yml`
- `Error response from daemon: pull access denied` → образ `printbot-backend:latest` не зібраний або не запушений у registry
- `port is already allocated` → конфлікт портів, перевір запущені контейнери

---

### `docker compose logs` повертає 504

```json
{"detail": "Таймаут отримання логів."}
```

Контейнер в поганому стані. Перевір вручну:
```bash
docker compose -p printbot_SUBDOMAIN ps
docker compose -p printbot_SUBDOMAIN logs --tail=20
```

---

### Помилка шифрування `InvalidToken`

```
cryptography.fernet.InvalidToken
```

`ENCRYPTION_KEY` в `.env` не відповідає ключу з яким шифрувались записи в БД. Можливо ключ змінили не мігрувавши дані. Відновити тільки з бекапу + старого ключа.

---

### Resource limits не працюють

Переконайся що використовується Docker Compose V2 (plugin, не standalone):
```bash
docker compose version
# Docker Compose version v2.x.x  ← правильно
```

`mem_limit` і `cpus` є Compose Spec параметрами і підтримуються починаючи з Compose V2.

---

## 14. Структура директорій на сервері

```
/opt/printbot/
├── manager/                         ← Код (git clone сюди)
│   ├── manager_app/
│   ├── alembic/
│   ├── requirements.txt
│   └── .env                         ← chmod 600, не в git
│
├── infrastructure/
│   ├── templates/
│   │   └── docker-compose.instance.yml
│   ├── docker-compose.traefik.yml
│   ├── update_all_instances.sh      ← chmod +x
│   └── backup_instance.sh          ← chmod +x
│
├── instances/                       ← Автоматично керується оркестратором
│   └── <subdomain>/
│       ├── .env                     ← chmod 600, генерується воркером
│       └── docker-compose.yml
│
└── backups/
    └── <subdomain>/
        ├── db_TIMESTAMP.sql
        └── config_TIMESTAMP.tar.gz
```
