#!/bin/bash

# Параметры подключения (используем суперпользователя)
SUPERUSER_URL='postgresql://postgres:ваш_пароль_postgres@192.168.0.4:5432/default_db'

# Или если postgres не имеет пароля:
# SUPERUSER_URL='postgresql://postgres@192.168.0.4:5432/default_db'

# Параметры нового пользователя
NEW_USER='EOS_user'
NEW_PASSWORD='vjAEWUO1FsCLAYjksgE4yAfb-ArxFI'
NEW_SCHEMA='EOS'

# Выполнение SQL команд через psql
psql "$SUPERUSER_URL" <<EOF
-- Создание нового пользователя (только если не существует)
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$NEW_USER') THEN
    CREATE USER "$NEW_USER" WITH PASSWORD '$NEW_PASSWORD';
    RAISE NOTICE 'Пользователь $NEW_USER создан';
  ELSE
    RAISE NOTICE 'Пользователь $NEW_USER уже существует';
  END IF;
END
\$\$;

-- Создание новой схемы (если не существует)
CREATE SCHEMA IF NOT EXISTS "$NEW_SCHEMA";

-- Выдача прав на схему новому пользователю
GRANT ALL PRIVILEGES ON SCHEMA "$NEW_SCHEMA" TO "$NEW_USER";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA "$NEW_SCHEMA" TO "$NEW_USER";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA "$NEW_SCHEMA" TO "$NEW_USER";
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA "$NEW_SCHEMA" TO "$NEW_USER";

-- Настройка прав по умолчанию для будущих объектов
ALTER DEFAULT PRIVILEGES IN SCHEMA "$NEW_SCHEMA" GRANT ALL ON TABLES TO "$NEW_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA "$NEW_SCHEMA" GRANT ALL ON SEQUENCES TO "$NEW_USER";
ALTER DEFAULT PRIVILEGES IN SCHEMA "$NEW_SCHEMA" GRANT ALL ON FUNCTIONS TO "$NEW_USER";

-- Проверка
\du
\dn
EOF

echo "Скрипт выполнен"