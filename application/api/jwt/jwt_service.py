# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from datetime import datetime, timedelta
import jwt
import hashlib
import time
from maintenance.database_connector import get_db_session
from maintenance.read_config import config
from maintenance.logger import setup_logger
from sqlalchemy import text

logger = setup_logger(__name__)

class JWTService:
    """
    Сервис для работы с JWT-токенами и управления сессиями с детальным логированием.
    """
    
    _secret = config.get('app.jwt_key')
    _access_expires = config.get('app.access_expires', 600)
    _refresh_expires = config.get('app.refresh_expires', 86400)
    _max_sessions = config.get('app.count_session', 5)

    @classmethod
    def generate_tokens(cls, user_id):
        """
        Генерация пары токенов (access и refresh) с детальным логированием.
        """
        try:
            logger.info(f"[Token Generation] Начало генерации токенов для user_id: {user_id}")
            logger.debug(f"[Token Generation] Параметры: access_expires={cls._access_expires}s, refresh_expires={cls._refresh_expires}s")
            
            start_time = time.perf_counter()
            
            # Подготовка payload для access токена
            access_exp = datetime.utcnow() + timedelta(seconds=cls._access_expires)
            access_payload = {
                'user_id': user_id,
                'exp': access_exp,
                'type': 'access'
            }
            logger.debug(f"[Token Generation] Access Token Payload: {access_payload}")
            logger.debug(f"[Token Generation] Access Token Expires: {access_exp.isoformat()}")
            
            # Генерация access токена
            access_token = jwt.encode(access_payload, cls._secret, algorithm='HS256')
            logger.debug(f"[Token Generation] Access Token (first 10 chars): {access_token[:10]}...")
            
            # Подготовка payload для refresh токена
            refresh_exp = datetime.utcnow() + timedelta(seconds=cls._refresh_expires)
            refresh_payload = {
                'user_id': user_id,
                'exp': refresh_exp,
                'type': 'refresh'
            }
            logger.debug(f"[Token Generation] Refresh Token Payload: {refresh_payload}")
            logger.debug(f"[Token Generation] Refresh Token Expires: {refresh_exp.isoformat()}")
            
            # Генерация refresh токена
            refresh_token = jwt.encode(refresh_payload, cls._secret, algorithm='HS256')
            logger.debug(f"[Token Generation] Refresh Token (first 10 chars): {refresh_token[:10]}...")
            
            # Расчет времени выполнения
            generation_time = time.perf_counter() - start_time
            logger.info(f"[Token Generation] Успешная генерация токенов для user_id: {user_id}")
            logger.debug(f"[Token Generation] Время генерации: {generation_time:.4f} секунд")
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': cls._access_expires
            }
            
        except jwt.PyJWTError as e:
            logger.error(f"[Token Generation] Ошибка JWT: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.critical(f"[Token Generation] Критическая ошибка: {str(e)}", exc_info=True)
            raise

    @classmethod
    def create_session(cls, user_id, access_token, refresh_token, user_agent, ip_address):
        """
        Создание сессии пользователя в БД с максимально подробным логированием.
        """
        try:
            logger.info(f"[Session Creation] Начало создания сессии для user_id: {user_id}")
            logger.debug(f"[Session Creation] Параметры: user_agent='{user_agent}', ip={ip_address}")
            logger.debug(f"[Session Creation] Access Token (first 10 chars): {access_token[:10]}...")
            logger.debug(f"[Session Creation] Refresh Token (first 10 chars): {refresh_token[:10]}...")
            
            start_time = time.perf_counter()
            
            # Проверка и очистка старых сессий
            cls._remove_old_sessions_if_needed(user_id)
            
            # Хеширование refresh токена
            refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            logger.debug(f"[Session Creation] Refresh Token Hash: {refresh_token_hash}")
            
            with get_db_session() as session:
                logger.debug("[Session Creation] Установлено соединение с БД")
                
                # Подготовка данных для вставки
                session_data = {
                    'user_id': user_id,
                    'access_token': access_token,
                    'refresh_token_hash': refresh_token_hash,
                    'user_agent': user_agent,
                    'ip_address': ip_address
                }
                logger.debug(f"[Session Creation] Данные сессии: {session_data}")
                
                # Выполнение SQL-запроса
                result = session.execute(
                    text("""
                        INSERT INTO sessions 
                        (user_id, access_token, refresh_token_hash, user_agent, ip_address, 
                         created_at, expires_at, is_revoked)
                        VALUES 
                        (:user_id, :access_token, :refresh_token_hash, :user_agent, :ip_address, 
                         NOW(), NOW() + INTERVAL '1 hour', FALSE)
                        RETURNING session_id, created_at, expires_at
                    """),
                    session_data
                )
                
                # Получение результатов вставки
                session_info = result.fetchone()
                session.commit()
                
                logger.debug(f"[Session Creation] Данные созданной сессии: {dict(session_info._asdict())}")
                
                # Расчет времени выполнения
                execution_time = time.perf_counter() - start_time
                logger.info(f"[Session Creation] Сессия успешно создана. ID: {session_info.session_id}")
                logger.debug(f"[Session Creation] Время выполнения: {execution_time:.4f} секунд")
                
        except Exception as e:
            logger.error(f"[Session Creation] Ошибка создания сессии: {str(e)}", exc_info=True)
            raise

    @classmethod
    def _remove_old_sessions_if_needed(cls, user_id):
        """
        Удаление старых сессий при превышении лимита с детальным логированием.
        """
        try:
            logger.debug(f"[Session Cleanup] Проверка сессий для user_id: {user_id}")
            
            with get_db_session() as session:
                # Получение количества активных сессий
                active_count = session.execute(
                    text("""
                        SELECT COUNT(*) FROM sessions 
                        WHERE user_id = :user_id 
                        AND is_revoked = FALSE 
                        AND expires_at > NOW()
                    """),
                    {'user_id': user_id}
                ).scalar()
                
                logger.debug(f"[Session Cleanup] Текущее количество активных сессий: {active_count}")
                
                if active_count >= cls._max_sessions:
                    logger.info(f"[Session Cleanup] Превышен лимит сессий ({cls._max_sessions}), удаление самой старой")
                    
                    # Получение ID самой старой сессии
                    oldest_session = session.execute(
                        text("""
                            SELECT session_id, created_at FROM sessions 
                            WHERE user_id = :user_id 
                            ORDER BY created_at ASC 
                            LIMIT 1
                        """),
                        {'user_id': user_id}
                    ).fetchone()
                    
                    if oldest_session:
                        logger.debug(f"[Session Cleanup] Удаляемая сессия: ID={oldest_session.session_id}, создана={oldest_session.created_at}")
                        
                        # Удаление сессии
                        delete_result = session.execute(
                            text("""
                                DELETE FROM sessions 
                                WHERE session_id = :session_id
                            """),
                            {'session_id': oldest_session.session_id}
                        )
                        session.commit()
                        
                        logger.info(f"[Session Cleanup] Сессия ID={oldest_session.session_id} успешно удалена")
                    else:
                        logger.warning("[Session Cleanup] Не найдены сессии для удаления")
                
        except Exception as e:
            logger.error(f"[Session Cleanup] Ошибка очистки сессий: {str(e)}", exc_info=True)
            raise

    @classmethod
    def get_user_by_credentials(cls, login):
        """
        Поиск пользователя по логину с детальным логированием.
        """
        try:
            logger.info(f"[User Auth] Поиск пользователя по логину: '{login}'")
            start_time = time.perf_counter()
            
            with get_db_session() as session:
                logger.debug("[User Auth] Установлено соединение с БД")
                
                # Выполнение запроса
                user = session.execute(
                    text("SELECT user_id, password FROM users WHERE userlogin = :login"),
                    {'login': login}
                ).fetchone()
                
                # Расчет времени выполнения
                query_time = time.perf_counter() - start_time
                
                if user:
                    logger.info(f"[User Auth] Пользователь найден: ID={user.user_id}")
                    logger.debug(f"[User Auth] Время выполнения запроса: {query_time:.4f} секунд")
                else:
                    logger.warning(f"[User Auth] Пользователь с логином '{login}' не найден")
                    logger.debug(f"[User Auth] Время выполнения запроса: {query_time:.4f} секунд")
                
                return user
                
        except Exception as e:
            logger.error(f"[User Auth] Ошибка поиска пользователя: {str(e)}", exc_info=True)
            raise