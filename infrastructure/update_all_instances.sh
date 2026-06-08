#!/bin/bash
# update_all_instances.sh — Rolling update всіх інстансів точок печати.
#
# Використання: ./update_all_instances.sh
#
# Що робить:
#   1. Підтягує актуальний Docker образ
#   2. Перебирає всі директорії інстансів
#   3. Перезапускає api та worker з новим образом
#   4. Запускає alembic міграції через compose exec (не docker ps grep!)
#
# # ВАЖЛИВО: Помилки всередині циклу обробляються через явний if/else —
# це дозволяє продовжити оновлення решти інстансів при збої одного.
# НЕ додавай команди всередині if/else без обробки помилок:
# set -e зупинить скрипт якщо команда поза if/else поверне ненульовий код.
set -euo pipefail: зупиняє скрипт при будь-якій помилці,
# невизначеній змінній або помилці в pipeline.

set -euo pipefail

INSTANCES_DIR="/opt/printbot/instances"
IMAGE="printbot-backend:latest"
FAILED_INSTANCES=()

echo "🚀 Запуск безпечного rolling update..."
echo "📦 Підтягуємо актуальний образ: $IMAGE"
docker pull "$IMAGE"

for dir in "$INSTANCES_DIR"/*/; do
    if [ ! -d "$dir" ]; then
        continue
    fi

    subdomain=$(basename "$dir")
    echo ""
    echo "════════════════════════════════════════"
    echo "🔄 Оновлення: $subdomain"

    # Перезапускаємо з новим образом через контекст проекту
    # (не docker ps grep — точне звернення до конкретного стеку)
    if docker compose \
        -p "printbot_$subdomain" \
        --project-directory "$dir" \
        up -d --no-build; then

        echo "⚙️  Міграції БД для $subdomain..."
        # compose exec замість 'docker exec $(docker ps -q -f name=...)' —
        # усуває ризик хибних збігів імен контейнерів
        docker compose \
            -p "printbot_$subdomain" \
            --project-directory "$dir" \
            exec -T api alembic upgrade head

        echo "✅ $subdomain оновлено успішно."
    else
        echo "❌ Помилка оновлення $subdomain. Пропускаємо."
        FAILED_INSTANCES+=("$subdomain")
    fi
done

echo ""
echo "════════════════════════════════════════"
if [ ${#FAILED_INSTANCES[@]} -eq 0 ]; then
    echo "🎉 Всі інстанси успішно оновлені!"
else
    echo "⚠️  Завершено з помилками у наступних інстансах:"
    for name in "${FAILED_INSTANCES[@]}"; do
        echo "   - $name"
    done
    exit 1
fi
