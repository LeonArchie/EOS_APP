# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from datetime import datetime, timedelta
import jwt
from maintenance.database_connector import get_db_session
from maintenance.read_config import config
from maintenance.logger import setup_logger
from sqlalchemy import text
import time

logger = setup_logger(__name__)

class JWTService:
    """
    Сервис для работы с JWT-токенами.
    """
    
    _secret = config.get('app.jwt_key')
    _access_expires = config.get('app.access_expires', 600)
    _refresh_expires = config.get('app.refresh_expires', 86400)

    @classmethod
    def generate_tokens(cls, user_id):
        """
        Генерация пары токенов (access и refresh)
        """
        try:
            logger.info(f"Начало генерации токенов для user_id: {user_id}")
            logger.debug(f"Используемые параметры: access_expires={cls._access_expires}, refresh_expires={cls._refresh_expires}")
            
            start_time = time.time()
            
            access_payload = {
                'user_id': user_id,
                'exp': datetime.utcnow() + timedelta(seconds=cls._access_expires),
                'type': 'access'
            }
            logger.debug(f"Payload access токена: {access_payload}")
            
            access_token = jwt.encode(access_payload, cls._secret, algorithm='HS256')
            
            refresh_payload = {
                'user_id': user_id,
                'exp': datetime.utcnow() + timedelta(seconds=cls._refresh_expires),
                'type': 'refresh'
            }
            logger.debug(f"Payload refresh токена: {refresh_payload}")
            
            refresh_token = jwt.encode(refresh_payload, cls._secret, algorithm='HS256')
            
            generation_time = time.time() - start_time
            logger.info(f"Токены успешно сгенерированы для user_id: {user_id}. Время генерации: {generation_time:.3f} сек")
            logger.debug(f"Access токен (первые 10 символов): {access_token[:10]}...")
            logger.debug(f"Refresh токен (первые 10 символов): {refresh_token[:10]}...")
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': cls._access_expires
            }
            
        except Exception as e:
            logger.critical(f"Ошибка генерации токенов для user_id {user_id}: {str(e)}", exc_info=True)
            raise

    @classmethod
    def create_session(cls, user_id, access_token, refresh_token):
        """
        Создание сессии пользователя в БД
        """
        try:
            logger.info(f"Создание сессии для user_id: {user_id}")
            logger.debug(f"Параметры сессии: access_token={access_token[:10]}..., refresh_token={refresh_token[:10]}...")
            
            start_time = time.time()
            
            with get_db_session() as session:
                logger.debug("Подключение к БД установлено, выполнение запроса")
                
                result = session.execute(
                    text("""
                        INSERT INTO sessions 
                        (user_id, access_token, refresh_token, expires_at)
                        VALUES 
                        (:user_id, :access_token, :refresh_token, NOW() + INTERVAL '1 hour')
                        RETURNING session_id
                    """),
                    {
                        'user_id': user_id,
                        'access_token': access_token,
                        'refresh_token': refresh_token
                    }
                )
                
                session_id = result.fetchone()[0]
                session.commit()
                
                execution_time = time.time() - start_time
                logger.info(f"Сессия создана успешно. ID сессии: {session_id}. Время выполнения: {execution_time:.3f} сек")
                
        except Exception as e:
            logger.error(f"Ошибка создания сессии для user_id {user_id}: {str(e)}", exc_info=True)
            raise

    @classmethod
    def get_user_by_credentials(cls, login):
        """
        Поиск пользователя по логину
        """
        try:
            logger.info(f"Поиск пользователя по логину: {login}")
            start_time = time.time()
            
            with get_db_session() as session:
                logger.debug("Выполнение запроса к БД для поиска пользователя")
                
                user = session.execute(
                    text("SELECT user_id, password FROM users WHERE userlogin = :login"),
                    {'login': login}
                ).fetchone()
                
                execution_time = time.time() - start_time
                
                if user:
                    logger.info(f"Пользователь найден: {login} (ID: {user.user_id}). Время поиска: {execution_time:.3f} сек")
                else:
                    logger.warning(f"Пользователь не найден: {login}. Время поиска: {execution_time:.3f} сек")
                    
                return user
                
        except Exception as e:
            logger.error(f"Ошибка поиска пользователя по логину {login}: {str(e)}", exc_info=True)
            raise