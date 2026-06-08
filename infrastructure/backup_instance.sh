#!/bin/bash
# backup_instance.sh — Резервна копія бази даних та конфігурації одного інстансу.
#
# Використання: ./backup_instance.sh <subdomain>
# Приклад:      ./backup_instance.sh odessa-center
#
# Що робить:
#   1. pg_dump через compose exec (точна адресація, не docker ps grep)
#   2. Запис у temp-файл → mv (атомарна операція, порожній файл не збережеться)
#   3. Архів конфігурації .env та docker-compose.yml
#   4. Явна перевірка кодів завершення на кожному кроці

set -uo pipefail

# :? — падати з повідомленням якщо параметр не переданий
SUBDOMAIN=${1:?"Вкажіть субдомен першим параметром (наприклад: odessa-center)"}

BACKUP_DIR="/opt/printbot/backups/$SUBDOMAIN"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEMP_SQL="$BACKUP_DIR/.db_${TIMESTAMP}.tmp.sql"
FINAL_SQL="$BACKUP_DIR/db_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "💾 Дамп бази даних для інстансу: $SUBDOMAIN"

# Використовуємо compose exec для точної адресації контейнера БД.
# Спочатку пишемо в temp-файл щоб уникнути збереження порожнього файлу при помилці.
if docker compose \
    -p "printbot_$SUBDOMAIN" \
    --project-directory "/opt/printbot/instances/$SUBDOMAIN" \
    exec -T db \
    pg_dump -U print_user print_instance_db > "$TEMP_SQL"; then

    # Атомарна операція: temp → final
    mv "$TEMP_SQL" "$FINAL_SQL"
    echo "✅ База збережена: $FINAL_SQL"
else
    echo "❌ Помилка: pg_dump не вдалося виконати для $SUBDOMAIN"
    rm -f "$TEMP_SQL"
    exit 1
fi

echo "📦 Архівація конфігурації..."
CONFIG_ARCHIVE="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"

if tar \
    --exclude=".env" \
    -czf "$CONFIG_ARCHIVE" \
    -C "/opt/printbot/instances/$SUBDOMAIN" .; then
    echo "✅ Конфігурація заархівована: $CONFIG_ARCHIVE"
    echo "ℹ️  .env виключено з архіву (містить секрети)."
else
    echo "❌ Помилка при архівації директорії інстансу."
    exit 1
fi

echo ""
echo "🎉 Бекап завершено: $BACKUP_DIR"
echo "   SQL дамп:    $(du -sh "$FINAL_SQL" | cut -f1)"
echo "   Конфіг:      $(du -sh "$CONFIG_ARCHIVE" | cut -f1)"
