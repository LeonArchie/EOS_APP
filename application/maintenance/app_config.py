# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import json
import time
from typing import Dict, Any
from maintenance.read_config import config
from maintenance.database_connector import get_db_connection_string
from maintenance.logger import setup_logger

# Инициализация логгера
logger = setup_logger(__name__)

def _log_config_step(step: str, details: str = "", level: str = "info") -> None:
    """Унифицированное логирование шагов конфигурации"""
    log_method = getattr(logger, level.lower(), logger.info)
    border = "=" * 50
    log_method(f"\n{border}\nCONFIG: {step}\n{details}\n{border}")

def get_app_config() -> Dict[str, Any]:
    """
    Получение и валидация конфигурации Flask-приложения с детальным логированием
    
    Возвращает:
        Dict[str, Any]: Словарь с настройками приложения:
            - SECRET_KEY: Ключ для подписи сессий
            - VERSION: Версия приложения
            - SQLALCHEMY_DATABASE_URI: Строка подключения к БД
            - SQLALCHEMY_TRACK_MODIFICATIONS: Флаг отслеживания изменений
            - DEBUG: Режим отладки
            
    Логирует:
        - Подробную информацию о каждом параметре конфигурации
        - Источник получения значений (конфиг или значения по умолчанию)
        - Время выполнения операции
    """
    start_time = time.time()
    config_source = {}
    
    try:
        _log_config_step("Начало загрузки конфигурации приложения")
        
        # Получение SECRET_KEY
        secret_key = config.get('app.flask_key', 'default-secret-key')
        config_source['SECRET_KEY'] = 'config' if 'app.flask_key' in config._config else 'default'
        logger.debug(f"Получен SECRET_KEY (источник: {config_source['SECRET_KEY']})")
        
        # Получение VERSION
        version = config.get('version', '0.0.0')
        config_source['VERSION'] = 'config' if 'version' in config._config else 'default'
        logger.debug(f"Получена VERSION (источник: {config_source['VERSION']}): {version}")
        
        # Получение строки подключения к БД
        db_uri = get_db_connection_string()
        config_source['SQLALCHEMY_DATABASE_URI'] = 'dynamic'
        logger.debug("Получена строка подключения к БД")
        
        # Получение режима отладки
        debug_mode = config.get('app.debug', False)
        config_source['DEBUG'] = 'config' if 'app' in config._config and 'debug' in config._config['app'] else 'default'
        logger.debug(f"Режим отладки: {'ВКЛ' if debug_mode else 'ВЫКЛ'} (источник: {config_source['DEBUG']})")
        
        # Формирование итоговой конфигурации
        app_config = {
            'SECRET_KEY': secret_key,
            'VERSION': version,
            'SQLALCHEMY_DATABASE_URI': db_uri,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'DEBUG': debug_mode
        }
        
        # Логирование итоговой конфигурации (без чувствительных данных)
        safe_config = app_config.copy()
        safe_config['SECRET_KEY'] = '***' if app_config['SECRET_KEY'] != 'default-secret-key' else 'default'
        safe_config['SQLALCHEMY_DATABASE_URI'] = '***'  # Скрываем строку подключения
        
        _log_config_step(
            "Конфигурация успешно загружена",
            f"Параметры (без чувствительных данных):\n"
            f"{json.dumps(safe_config, indent=2)}\n"
            f"Источники параметров:\n"
            f"{json.dumps(config_source, indent=2)}\n"
            f"Время загрузки: {(time.time() - start_time) * 1000:.2f} мс"
        )
        
        return app_config
        
    except Exception as e:
        _log_config_step(
            "Ошибка загрузки конфигурации",
            f"Тип ошибки: {type(e).__name__}\n"
            f"Сообщение: {str(e)}\n"
            f"Время до ошибки: {(time.time() - start_time) * 1000:.2f} мс",
            "error"
        )
        raise RuntimeError("Не удалось загрузить конфигурацию приложения") from e

def log_config_summary(config: Dict[str, Any]) -> None:
    """
    Логирование итоговой конфигурации приложения с маскировкой чувствительных данных
    
    Параметры:
        config (Dict[str, Any]): Конфигурация приложения
    """
    try:
        # Создаем безопасную версию конфигурации для логирования
        safe_config = {
            'VERSION': config.get('VERSION', 'unknown'),
            'DEBUG': config.get('DEBUG', False),
            'SQLALCHEMY_TRACK_MODIFICATIONS': config.get('SQLALCHEMY_TRACK_MODIFICATIONS', False),
            'SECRET_KEY': '***' if config.get('SECRET_KEY') else 'not-set',
            'SQLALCHEMY_DATABASE_URI': '***' if config.get('SQLALCHEMY_DATABASE_URI') else 'not-set'
        }
        
        _log_config_step(
            "Итоговая конфигурация приложения",
            f"Безопасная версия конфигурации:\n{json.dumps(safe_config, indent=2)}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка логирования конфигурации: {str(e)}", exc_info=True)