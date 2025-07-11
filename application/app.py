# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Flask, jsonify, request
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_engine
from sqlalchemy import text
import time
import logging
from api.health.health import init_health_route
import json
from datetime import datetime

logger = setup_logger(__name__)

def log_request_response(response):
    """Логирование информации о запросе и ответе"""
    try:
        # Основные данные запроса
        log_message = (
            f"{request.method} {request.path} - {response.status_code}\n"
            f"From: {request.remote_addr}\n"
            f"Headers: {dict(request.headers)}\n"
            f"Query: {dict(request.args)}"
        )

        # Добавляем тело запроса, если есть
        if request.content_type not in ['multipart/form-data', 'application/octet-stream']:
            try:
                if request.data:
                    request_body = request.get_json(silent=True) or request.data.decode('utf-8')
                    log_message += f"\nRequest Body: {request_body}"
            except Exception as e:
                log_message += f"\nRequest Body Error: {str(e)}"

        # Добавляем тело ответа, если это JSON или текст
        try:
            if response.content_type == 'application/json':
                log_message += f"\nResponse Body: {json.loads(response.get_data(as_text=True))}"
            elif 'text/' in response.content_type:
                log_message += f"\nResponse Body: {response.get_data(as_text=True)}"
        except Exception as e:
            log_message += f"\nResponse Body Error: {str(e)}"

        logger.info(log_message)
        
    except Exception as e:
        logger.error(f"Failed to log request/response: {str(e)}")

    return response

def wait_for_database_connection():
    """Ожидание успешного подключения к базе данных"""
    max_retries = config.get('db.max_retries', 5)
    retry_delay = config.get('db.retry_delay', 5)
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"Попытка подключения к базе данных ({retry_count + 1}/{max_retries})")
            engine = get_db_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Подключение к базе данных успешно установлено")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
    
    logger.critical(f"Не удалось установить подключение к базе данных после {max_retries} попыток")
    return False

def create_app():
    """Фабрика для создания Flask-приложения"""
    logger.info("Создание Flask-приложения")
    
    try:
        if not wait_for_database_connection():
            raise RuntimeError("Не удалось подключиться к базе данных")

        app = Flask(__name__)
        
        app_config = {
            'SECRET_KEY': config.get('app.flask_key', 'default-secret-key'),
            'VERSION': config.get('version', '0.0.0'),
            'SQLALCHEMY_DATABASE_URI': f"postgresql://{config.get('db.user')}:{config.get('db.password')}@{config.get('db.master_host')}:{config.get('db.master_port')}/{config.get('db.database')}",
            'SQLALCHEMY_TRACK_MODIFICATIONS': False
        }
        
        app.config.update(app_config)
        
        # Добавляем обработчики для логирования запросов/ответов
        @app.before_request
        def log_request_info():
            logger.info(
                f"Incoming request: {request.method} {request.path}\n"
                f"From: {request.remote_addr}\n"
                f"Headers: {dict(request.headers)}\n"
                f"Query: {dict(request.args)}"
            )
        
        @app.after_request
        def after_request(response):
            log_request_response(response)
            return response
        
        # Инициализация health check роута
        init_health_route(app)
        
        # Обработка 404 ошибки
        @app.errorhandler(404)
        def not_found(error):
            response = jsonify({
                "status": False,
                "code": 404,
                "body": {
                    "message": "Not Found"
                }
            })
            response.status_code = 404
            return response
        
        logger.info("Flask-приложение успешно создано")
        return app
        
    except Exception as e:
        logger.critical(f"ОШИБКА СОЗДАНИЯ ПРИЛОЖЕНИЯ: {str(e)}")
        raise

# Создание экземпляра приложения
try:
    logger.info("Инициализация основного приложения")
    app = create_app()
    logger.info("Приложение готово к работе")
except Exception as e:
    logger.critical(f"НЕУДАЛОСЬ ЗАПУСТИТЬ ПРИЛОЖЕНИЕ: {str(e)}")
    raise

if __name__ == '__main__':
    host = config.get('app.address', '0.0.0.0')
    port = config.get('app.port', 5000)
    logger.info(f"Запуск сервера разработки на {host}:{port}")
    try:
        app.run(host=host, port=port)
        logger.info("Сервер разработки успешно запущен")
    except Exception as e:
        logger.critical(f"ОШИБКА ЗАПУСКА СЕРВЕРА: {str(e)}")
        raise