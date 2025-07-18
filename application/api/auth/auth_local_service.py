# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import hashlib
import time
from maintenance.database_connector import get_db_session
from maintenance.logger import setup_logger
from sqlalchemy import text

logger = setup_logger(__name__)

class AuthService:
    """
    Сервис для работы с аутентификацией пользователей (без логики токенов).
    """

    @staticmethod
    def get_user_by_credentials(login):
        """
        Поиск пользователя по логину с детальным логированием.
        Возвращает пользователя с полями user_id и password_hash.
        """
        try:
            logger.info(f"[User Auth] Поиск пользователя по логину: '{login}'")
            start_time = time.perf_counter()
            
            with get_db_session() as session:
                logger.debug("[User Auth] Установлено соединение с БД")
                
                # Выполнение запроса с использованием password_hash вместо password
                user = session.execute(
                    text("SELECT user_id, password_hash FROM users WHERE userlogin = :login"),
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

    @staticmethod
    def verify_password(input_password_hash, stored_password_hash):
        """
        Проверка соответствия хеша введенного пароля и хеша из БД.
        """
        try:
            logger.debug("[Password Verification] Проверка хешей паролей")
            logger.debug(f"Сравнение хешей: input='{input_password_hash}', stored='{stored_password_hash}'")
            return input_password_hash == stored_password_hash
        except Exception as e:
            logger.error(f"[Password Verification] Ошибка проверки пароля: {str(e)}", exc_info=True)
            raise