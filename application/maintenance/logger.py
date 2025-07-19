# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import logging
import sys
import os
from typing import Optional

# =============================================
#           НАСТРОЙКИ ЛОГИРОВАНИЯ
# =============================================

LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-20s | pid:%(process)d | %(module)s:%(funcName)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = logging.DEBUG

# =============================================
#           ФУНКЦИЯ НАСТРОЙКИ ЛОГГЕРА
# =============================================

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Настраивает логгер с расширенными возможностями логирования.
    
    Параметры:
        name (str, optional): Имя логгера (обычно __name__). 
                             Если None, вернет корневой логгер.
    
    Возвращает:
        logging.Logger: Настроенный экземпляр логгера
    
    Особенности:
        - Поддержка PID процесса
        - Перехват необработанных исключений
        - Раздельный вывод INFO/DEBUG (stdout) и WARNING+/ERROR (stderr)
        - Детальный формат с указанием модуля и функции
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Очистка существующих обработчиков
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Создаем форматтер
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Обработчик для INFO и DEBUG (stdout)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)
    logger.addHandler(stdout_handler)
    
    # Обработчик для WARNING и выше (stderr)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.WARNING)
    logger.addHandler(stderr_handler)
    
    # Настройка перехвата необработанных исключений
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Необработанное исключение",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    sys.excepthook = handle_exception
    
    logger.debug(f"Логгер инициализирован (PID: {os.getpid()})")
    
    return logger