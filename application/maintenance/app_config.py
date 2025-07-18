# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from maintenance.read_config import config
from maintenance.database_connector import get_db_connection_string
from maintenance.logger import setup_logger

# Инициализация логгера
logger = setup_logger(__name__)

def get_app_config():
    """
    Получение конфигурации Flask-приложения
    :return: Словарь с настройками приложения:
        - SECRET_KEY: Ключ для подписи сессий
        - VERSION: Версия приложения
        - SQLALCHEMY_DATABASE_URI: Строка подключения к БД
        - SQLALCHEMY_TRACK_MODIFICATIONS: Флаг отслеживания изменений
    """
    logger.debug("Получение конфигурации приложения")
    return {
        'SECRET_KEY': config.get('app.flask_key', 'default-secret-key'),
        'VERSION': config.get('version', '0.0.0'),
        'SQLALCHEMY_DATABASE_URI': get_db_connection_string(),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DEBUG': config.get('app.debug', False)
    }