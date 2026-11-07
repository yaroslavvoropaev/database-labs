#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d

echo 'Пересоздаю базу данных...'
docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U chicken-farm -d postgres <<'SQL'
DROP DATABASE IF EXISTS "chicken-farm" WITH (FORCE);
CREATE DATABASE "chicken-farm" OWNER "chicken-farm";
SQL

echo 'Жду готовности PostgreSQL...'
until docker compose exec -T postgres pg_isready -h 127.0.0.1 -U chicken-farm -d chicken-farm >/dev/null 2>&1; do
    sleep 1
done

psql() { docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U chicken-farm -d chicken-farm "$@"; }

echo 'Создаю схему (schema.sql)...'
psql < src/main/resources/schema.sql 2>&1 | grep -v 'does not exist, skipping' || true
echo 'Загружаю справочники (seed.sql)...'
psql < src/main/resources/seed.sql

if [ ! -x .venv/bin/python ]; then
    echo 'Создаю виртуальное окружение Python...'
    python3 -m venv .venv
    .venv/bin/pip install -q -r scripts/requirements.txt
fi
echo 'Генерирую тестовые данные...'
.venv/bin/python scripts/generate_test_data.py
