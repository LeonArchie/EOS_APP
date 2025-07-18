# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Flask
from maintenance.logger import setup_logger
from maintenance.database_utils import wait_for_database_connection
from maintenance.request_logging import log_request_info, log_request_response
from maintenance.app_config import get_app_config
from api.error_handlers import not_found
from api.health.health import health_bp
from maintenance.read_config import config
from api.auth.local_auth import local_auth_bp
from maintenance.request_validator import RequestValidator
from maintenance.migration import run_migrations, MigrationError

# Инициализация логгера
logger = setup_logger(__name__)

def create_app():
    """
    Фабрика для создания и настройки Flask-приложения.
    """
    logger.info("Начало создания Flask-приложения")
    
    try:
        app = Flask(__name__)
        logger.debug("Экземпляр Flask создан")

        # Загрузка конфигурации
        app.config.update(get_app_config())
        logger.debug("Конфигурация приложения загружена")

        # Инициализация валидатора запросов
        validator = RequestValidator()
        validator.init_app(app)
        logger.info("Валидатор запросов инициализирован")

        # Инициализация подключения к базе данных
        logger.info("Инициализация подключения к базе данных")
        from maintenance.database_connector import initialize_database
        initialize_database()
        
        # Проверка подключения к БД
        if not wait_for_database_connection():
            logger.critical("Не удалось установить подключение к базе данных")
            raise RuntimeError("Не удалось подключиться к базе данных")
        
        # Выполнение миграций
        try:
            logger.info("Проверка и выполнение миграций БД")
            run_migrations()
        except MigrationError as e:
            logger.critical(f"Ошибка выполнения миграций: {str(e)}")
            raise RuntimeError("Не удалось выполнить миграции БД")

        logger.info("Подключение к базе данных успешно установлено")

        # Регистрация middleware
        app.before_request(log_request_info)
        app.after_request(log_request_response)
        logger.debug("Middleware для логирования зарегистрированы")

        # Регистрация обработчиков ошибок
        app.errorhandler(404)(not_found)
        logger.debug("Обработчики ошибок зарегистрированы")

        # Регистрация blueprint'ов
        app.register_blueprint(health_bp)
        app.register_blueprint(local_auth_bp)
        logger.info("Blueprint'ы успешно зарегистрированы")

        logger.info("Flask-приложение успешно создано и настроено")
        return app
        
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ СОЗДАНИИ ПРИЛОЖЕНИЯ: {str(e)}", exc_info=True)
        raise

# Создание экземпляра приложения
try:
    logger.info("Инициализация основного приложения")
    app = create_app()
    logger.info("Приложение готово к работе")
except Exception as e:
    logger.critical(f"НЕУДАЛОСЬ ЗАПУСТИТЬ ПРИЛОЖЕНИЕ: {str(e)}", exc_info=True)
    raise   

if __name__ == "__main__":
    logger.info(f"Запуск сервера на {config.get('app.address', '0.0.0.0')}:{config.get('app.port', 9443)}")
    app.run(
        host=config.get('app.address', '0.0.0.0'), 
        port=config.get('app.port', 9443),
        debug=config.get('app.debug', False)
    )
    logger.info("Сервер остановлен")