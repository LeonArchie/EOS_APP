# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import logging
import sys

# =============================================
#           НАСТРОЙКИ ЛОГИРОВАНИЯ
# =============================================

LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# =============================================
#           ФУНКЦИЯ НАСТРОЙКИ ЛОГГЕРА
# =============================================

def setup_logger(name: str) -> logging.Logger:
    """
    Настройка логгера для работы с systemd
    
    :param name: имя логгера (обычно __name__)
    :return: настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Очистка существующих обработчиков
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Форматтер для логов
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Единственный обработчик - вывод в stdout
    # systemd сам перенаправит его согласно конфигурации сервиса
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger