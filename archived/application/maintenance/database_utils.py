# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import logging
import time
import json
from typing import Optional
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from maintenance.logger import setup_logger
from maintenance.database_connector import get_db_engine
from sqlalchemy import text
from maintenance.read_config import config

logger = setup_logger(__name__)

def _log_db_connection_step(step: str, details: str = "", level: str = "info") -> None:
    """Унифицированное логирование шагов подключения к БД"""
    log_method = getattr(logger, level.lower(), logger.info)
    border = "-" * 60
    log_method(f"\n{border}\nПОДКЛЮЧЕНИЕ К БД: {step}\n{details}\n{border}")

def wait_for_database_connection(retries: Optional[int] = None, delay: Optional[float] = None) -> bool:
    """
    Ожидание успешного подключения к базе данных с экспоненциальной задержкой
    и детальным логированием всех этапов
    
    Параметры:
        retries (Optional[int]): Максимальное количество попыток (None для значения из конфига)
        delay (Optional[float]): Базовая задержка между попытками в секундах (None для значения из конфига)
        
    Возвращает:
        bool: True если подключение установлено, False если все попытки исчерпаны
    """
    # Получение параметров из конфига с fallback значениями
    max_retries = retries if retries is not None else config.get('db.max_retries', 5)
    base_retry_delay = delay if delay is not None else config.get('db.retry_delay', 5)
    
    _log_db_connection_step(
        "Начало подключения к БД",
        f"Макс. попыток: {max_retries}\n"
        f"Базовая задержка: {base_retry_delay} сек\n"
        f"Стратегия задержки: экспоненциальная"
    )
    
    start_time = time.time()
    last_error: Optional[str] = None
    
    for attempt in range(1, max_retries + 1):
        attempt_start = time.time()
        try:
            # Логирование начала попытки подключения
            _log_db_connection_step(
                f"Попытка подключения {attempt}/{max_retries}",
                f"Время с начала: {time.time() - start_time:.2f} сек"
            )
            
            logger.debug("Получение engine для подключения к БД")
            engine = get_db_engine()
            
            # Детальное логирование параметров подключения
            if logger.isEnabledFor(logging.DEBUG):
                db_params = {
                    'driver': engine.driver,
                    'host': engine.url.host,
                    'port': engine.url.port,
                    'database': engine.url.database,
                    'username': engine.url.username,
                    'pool_size': engine.pool.size(),
                    'pool_timeout': engine.pool.timeout(),
                }
                logger.debug(f"Параметры подключения:\n{json.dumps(db_params, indent=2)}")
            
            logger.debug("Установка соединения с БД")
            with engine.connect() as conn:
                # Проверка соединения
                logger.debug("Выполнение тестового запроса (SELECT 1)")
                with conn.begin():
                    result = conn.execute(text("SELECT 1"))
                    row = result.fetchone()
                    logger.debug(f"Результат тестового запроса: {row[0]}")
                
                # Дополнительная диагностика
                if logger.isEnabledFor(logging.DEBUG):
                    try:
                        version = conn.execute(text("SELECT version()")).fetchone()[0]
                        logger.debug(f"Версия СУБД: {version}")
                    except Exception as e:
                        logger.debug(f"Не удалось получить версию СУБД: {str(e)}")
                
                conn.close()  # Явное закрытие соединения
                logger.debug("Соединение с БД закрыто")
            
            # Успешное подключение
            total_time = time.time() - start_time
            _log_db_connection_step(
                "Подключение успешно установлено",
                f"Попытка: {attempt}/{max_retries}\n"
                f"Общее время: {total_time:.2f} сек\n"
                f"Время попытки: {time.time() - attempt_start:.2f} сек"
            )
            return True
            
        except OperationalError as e:
            last_error = str(e)
            logger.warning(
                f"Ошибка подключения к БД (попытка {attempt}): {last_error}",
                exc_info=True
            )
            
            if attempt < max_retries:
                # Экспоненциальная задержка с джиттером
                current_delay = base_retry_delay * (1.5 ** (attempt - 1))
                current_delay = min(current_delay, 30)  # Максимальная задержка 30 сек
                
                _log_db_connection_step(
                    "Повторная попытка",
                    f"Следующая попытка через {current_delay:.1f} сек\n"
                    f"Причина: {last_error}",
                    "warning"
                )
                time.sleep(current_delay)
                
        except SQLAlchemyError as e:
            last_error = str(e)
            logger.error(
                f"Критическая ошибка SQLAlchemy (попытка {attempt}): {last_error}",
                exc_info=True
            )
            break
            
        except Exception as e:
            last_error = str(e)
            logger.critical(
                f"Непредвиденная ошибка (попытка {attempt}): {last_error}",
                exc_info=True
            )
            break
    
    # Все попытки исчерпаны или критическая ошибка
    total_time = time.time() - start_time
    _log_db_connection_step(
        "Не удалось подключиться к БД",
        f"Исчерпано попыток: {max_retries}\n"
        f"Общее время: {total_time:.2f} сек\n"
        f"Последняя ошибка: {last_error}",
        "critical"
    )
    return False