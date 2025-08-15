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
            # Логирование начала операции
            logger.info(f"[DB Query Init] Запрос пользователя по логину. Login: '{login}'")
            start_time = time.perf_counter()
            db_conn_time = None
            
            with get_db_session() as session:
                # Логирование успешного подключения к БД
                db_conn_time = time.perf_counter() - start_time
                logger.debug(f"[DB Connection] Установлено соединение с БД. Время подключения: {db_conn_time:.4f} сек")
                
                # Подготовка и выполнение SQL запроса
                sql_query = "SELECT user_id, password_hash FROM users WHERE userlogin = :login"
                logger.debug(f"[SQL Execute] Выполнение запроса: {sql_query} с параметрами: login='{login}'")
                
                query_start = time.perf_counter()
                user = session.execute(
                    text(sql_query),
                    {'login': login}
                ).fetchone()
                
                # Расчет времени выполнения запроса
                query_exec_time = time.perf_counter() - query_start
                total_time = time.perf_counter() - start_time
                
                if user:
                    # Логирование успешного нахождения пользователя
                    logger.info(
                        f"[User Found] Пользователь найден. "
                        f"ID: {user.user_id}, "
                        f"Query Time: {query_exec_time:.4f} сек, "
                        f"Total Time: {total_time:.4f} сек"
                    )
                    logger.debug(f"[User Details] UserID: {user.user_id}, PasswordHash: [REDACTED]")
                else:
                    # Логирование отсутствия пользователя
                    logger.warning(
                        f"[User Not Found] Пользователь с логином '{login}' не найден. "
                        f"Query Time: {query_exec_time:.4f} сек, "
                        f"Total Time: {total_time:.4f} сек"
                    )
                
                return user
                
        except Exception as e:
            # Логирование ошибок с дополнительной информацией
            error_time = time.perf_counter() - start_time if 'start_time' in locals() else 0
            logger.critical(
                f"[DB Query Failed] Ошибка поиска пользователя '{login}'. "
                f"Error: {type(e).__name__}: {str(e)}, "
                f"Time Elapsed: {error_time:.4f} сек",
                exc_info=True
            )
            raise

    @staticmethod
    def verify_password(input_password_hash, stored_password_hash):
        """
        Проверка соответствия хеша введенного пароля и хеша из БД.
        """
        try:
            # Логирование начала проверки пароля
            logger.debug(
                "[Password Verify] Начало проверки хешей паролей. "
                f"InputHash: [REDACTED], StoredHash: [REDACTED]"
            )
            start_time = time.perf_counter()
            
            # Выполнение сравнения хешей
            result = input_password_hash == stored_password_hash
            
            # Логирование результата и времени выполнения
            exec_time = time.perf_counter() - start_time
            if result:
                logger.debug(
                    f"[Password Match] Хеши паролей совпадают. "
                    f"Время проверки: {exec_time:.6f} сек"
                )
            else:
                logger.warning(
                    f"[Password Mismatch] Хеши паролей не совпадают. "
                    f"Время проверки: {exec_time:.6f} сек"
                )
            
            return result
            
        except Exception as e:
            # Логирование ошибок при проверке пароля
            logger.error(
                f"[Password Verify Error] Ошибка проверки пароля. "
                f"Error: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise