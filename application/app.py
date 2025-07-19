# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Flask, request
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
import time

# Инициализация логгера с более подробным именем
logger = setup_logger('app.factory')

def create_app():
    """
    Фабрика для создания и настройки Flask-приложения.
    Возвращает:
        Flask: Экземпляр Flask-приложения
    Вызывает:
        RuntimeError: Если не удалось создать приложение
    """
    start_time = time.time()
    logger.info("Начало создания Flask-приложения")
    
    try:
        # 1. Создание экземпляра Flask
        logger.debug("Создание экземпляра Flask...")
        app = Flask(__name__)
        logger.info("Экземпляр Flask успешно создан")

        # 2. Загрузка конфигурации
        logger.debug("Загрузка конфигурации приложения...")
        app_config = get_app_config()
        app.config.update(app_config)
        logger.info(f"Конфигурация приложения загружена. Режим отладки: {app.config.get('DEBUG')}")

        # 3. Инициализация валидатора запросов
        logger.debug("Инициализация валидатора запросов...")
        validator = RequestValidator()
        validator.init_app(app)
        logger.info("Валидатор запросов успешно инициализирован")

        # 4. Работа с базой данных
        logger.info("Инициализация подключения к базе данных...")
        from maintenance.database_connector import initialize_database
        initialize_database()
        
        logger.debug("Проверка подключения к БД...")
        db_max_retries = config.get('db.max_retries', 5)  # Значение из конфига или 5 по умолчанию
        db_retry_delay = config.get('db.retry_delay', 5)  # Значение из конфига или 5 по умолчанию

        if not wait_for_database_connection(retries=db_max_retries, delay=db_retry_delay):
            logger.critical("Не удалось установить подключение к базе данных после нескольких попыток")
            raise RuntimeError("Не удалось подключиться к базе данных")
        
        # 5. Миграции базы данных
        try:
            logger.info("Проверка и выполнение миграций БД...")
            migration_results = run_migrations()
            logger.info(f"Миграции успешно выполнены. Применено {len(migration_results)} миграций")
        except MigrationError as e:
            logger.critical(f"Ошибка выполнения миграций: {str(e)}", exc_info=True)
            raise RuntimeError("Не удалось выполнить миграции БД")

        logger.info("Подключение к базе данных успешно установлено")

        # 6. Регистрация middleware
        app.before_request(log_request_info)
        app.after_request(log_request_response)
        logger.debug("Middleware для логирования успешно зарегистрированы")

        # 7. Обработчики ошибок
        app.errorhandler(404)(not_found)
        logger.debug("Обработчики ошибок успешно зарегистрированы")

        # 8. Регистрация blueprint'ов
        logger.debug("Регистрация blueprint'ов...")
        app.register_blueprint(health_bp)
        app.register_blueprint(local_auth_bp)
        logger.info(f"Зарегистрированы blueprint'ы: {', '.join([bp.name for bp in app.blueprints.values()])}")

        total_time = time.time() - start_time
        logger.info(f"Flask-приложение успешно создано и настроено за {total_time:.2f} секунд")
        return app
        
    except Exception as e:
        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ СОЗДАНИИ ПРИЛОЖЕНИЯ: {str(e)}", exc_info=True)
        raise

# Создание экземпляра приложения
try:
    logger.info("Инициализация основного приложения...")
    app = create_app()
    logger.info("Приложение успешно инициализировано и готово к работе")
except Exception as e:
    logger.critical(f"НЕУДАЛОСЬ ЗАПУСТИТЬ ПРИЛОЖЕНИЕ: {str(e)}", exc_info=True)
    raise   

if __name__ == "__main__":
    host = config.get('app.address', '0.0.0.0')
    port = config.get('app.port', 9443)
    debug_mode = config.get('app.debug', False)
    
    logger.info(f"Запуск сервера на {host}:{port} (режим отладки: {'включен' if debug_mode else 'выключен'})")
    try:
        app.run(host=host, port=port, debug=debug_mode)
    except Exception as e:
        logger.critical(f"ОШИБКА ПРИ РАБОТЕ СЕРВЕРА: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Сервер остановлен")