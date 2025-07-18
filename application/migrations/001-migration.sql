-- Создание таблицы пользователей
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    userlogin TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

COMMENT ON TABLE users IS 'Таблица пользователей системы';
COMMENT ON COLUMN users.user_id IS 'Уникальный идентификатор пользователя';
COMMENT ON COLUMN users.userlogin IS 'Логин пользователя';
COMMENT ON COLUMN users.password IS 'Хэш пароля пользователя';