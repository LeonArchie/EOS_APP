-- SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
-- Copyright (C) 2025 Петунин Лев Михайлович

-- Создание функции для обновления временных меток
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Создание триггера
CREATE TRIGGER update_users_timestamp
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- Комментарии
COMMENT ON FUNCTION update_timestamp() IS 'Функция для автоматического обновления поля updated_at текущей датой и временем';
COMMENT ON TRIGGER update_users_timestamp ON users IS 'Триггер для автоматического обновления поля updated_at при изменении данных пользователя';