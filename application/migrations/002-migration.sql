-- Создание таблицы сессий
CREATE TABLE sessions (
    session_id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id),
    access_token TEXT NOT NULL,
    refresh_token_hash TEXT NOT NULL,
    user_agent TEXT,
    ip_address TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    last_used_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE sessions IS 'Таблица сессий пользователей';
COMMENT ON COLUMN sessions.user_id IS 'Ссылка на пользователя';
COMMENT ON COLUMN sessions.access_token IS 'Токен доступа';
COMMENT ON COLUMN sessions.refresh_token_hash IS 'Хэш токена обновления';

-- Создание индексов
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_access_token ON sessions(access_token);