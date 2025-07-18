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

logger = setup_logger(__name__)

def create_app():
    """Фабрика для создания Flask-приложения"""
    logger.info("Создание Flask-приложения")
    
    try:
        app = Flask(__name__)
        app.config.update(get_app_config())
        
        # Инициализация БД после создания приложения
        from maintenance.database_connector import initialize_database
        initialize_database()
        
        # Проверка подключения
        if not wait_for_database_connection():
            raise RuntimeError("Не удалось подключиться к базе данных")
        
        app.before_request(log_request_info)
        app.after_request(log_request_response)
        app.register_blueprint(health_bp)
        app.errorhandler(404)(not_found)
        
        logger.info("Flask-приложение успешно создано")
        return app
        
    except Exception as e:
        logger.critical(f"ОШИБКА СОЗДАНИЯ ПРИЛОЖЕНИЯ: {str(e)}", exc_info=True)
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
    app.run(host=config.get('app.address', '0.0.0.0'), 
            port=config.get('app.port', 9443),
            debug=False)
    logger.info("Сервер запущен")