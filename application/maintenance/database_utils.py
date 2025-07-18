# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import time
from sqlalchemy.exc import OperationalError
from maintenance.logger import setup_logger
from maintenance.database_connector import get_db_engine
from sqlalchemy import text
from maintenance.read_config import config

logger = setup_logger(__name__)

def wait_for_database_connection():
    """Ожидание успешного подключения к базе данных с экспоненциальной задержкой"""
    max_retries = config.get('db.max_retries', 5)
    retry_delay = config.get('db.retry_delay', 5)
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Попытка подключения к БД ({attempt}/{max_retries})")
            engine = get_db_engine()
            
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("SELECT 1"))
                conn.close()  # Явное закрытие соединения
            
            logger.info("Подключение к базе данных успешно установлено")
            return True
            
        except OperationalError as e:
            logger.warning(f"Временная ошибка подключения: {str(e)}", exc_info=True)
            if attempt < max_retries:
                delay = retry_delay * (attempt * 0.5)
                logger.info(f"Повторная попытка через {delay:.1f} секунд...")
                time.sleep(delay)
        except Exception as e:
            logger.error(f"Критическая ошибка подключения: {str(e)}", exc_info=True)
            break
    
    logger.critical(f"Не удалось установить подключение к базе данных после {max_retries} попыток")
    return False