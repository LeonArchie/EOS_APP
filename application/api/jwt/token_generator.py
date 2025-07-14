# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import jwt
from datetime import datetime, timedelta
from uuid import uuid4
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_session
from sqlalchemy import text

logger = setup_logger(__name__)

class JWTGenerator:
    def __init__(self):
        self.secret_key = config.get('app.jwt_key')
        self.access_expires = timedelta(seconds=config.get('app.access_expires', 600))
        self.refresh_expires = timedelta(seconds=config.get('app.refresh_expires', 1200))
        self.max_sessions = config.get('app.count_session', 5)

    def create_tokens(self, user_id: str) -> dict:
        """Генерация новой пары токенов"""
        session_id = str(uuid4())
        
        access_token = jwt.encode({
            'user_id': user_id,
            'session_id': session_id,
            'exp': datetime.utcnow() + self.access_expires,
            'type': 'access'
        }, self.secret_key, algorithm='HS256')
        
        refresh_token = jwt.encode({
            'user_id': user_id,
            'session_id': session_id,
            'exp': datetime.utcnow() + self.refresh_expires,
            'type': 'refresh'
        }, self.secret_key, algorithm='HS256')
        
        self._add_user_session(user_id, session_id)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_id': session_id
        }

    def check_user_sessions(self, user_id: str) -> bool:
        """Проверка лимита сессий"""
        with get_db_session() as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM active_sessions WHERE user_id = :user_id"),
                {'user_id': user_id}
            ).scalar()
            return count < self.max_sessions

    def _add_user_session(self, user_id: str, session_id: str):
        """Добавление сессии в БД"""
        with get_db_session() as session:
            session.execute(
                text("""
                    INSERT INTO active_sessions (user_id, session_id)
                    VALUES (:user_id, :session_id)
                """),
                {'user_id': user_id, 'session_id': session_id}
            )
            session.commit()