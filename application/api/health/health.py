# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, jsonify
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import time

logger = setup_logger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health_check():
    """
    Проверка работоспособности сервиса.
    """
    try:
        logger.info("Запуск проверки работоспособности сервиса")
        logger.debug(f"Конфигурация приложения: version={config.get('version', '0.0.0')}")
        
        db_status = False
        db_error = None
        db_response_time = None
        
        try:
            logger.debug("Попытка получения engine базы данных")
            start_time = time.time()
            engine = get_db_engine()
            
            logger.debug("Попытка установления соединения с БД")
            with engine.connect() as conn:
                logger.debug("Выполнение тестового запроса к БД")
                result = conn.execute(text("SELECT 1"))
                db_status = bool(result)
                db_response_time = time.time() - start_time
                logger.info(f"Проверка БД выполнена успешно. Время ответа: {db_response_time:.3f} сек")
                
        except SQLAlchemyError as db_e:
            db_error = str(db_e)
            logger.error(f"Ошибка SQLAlchemy при проверке БД: {db_error}", exc_info=True)
        except Exception as db_e:
            db_error = str(db_e)
            logger.critical(f"Неожиданная ошибка при проверке БД: {db_error}", exc_info=True)

        response_data = {
            "status": True,
            "code": 200,
            "body": {
                "app_version": config.get('version', '0.0.0'),
                "database_available": db_status,
            }
        }
        
        logger.info(f"Проверка здоровья завершена. Статус БД: {'OK' if db_status else 'ERROR'}")
        if db_error:
            logger.debug(f"Детали ошибки БД: {db_error}")
            response_data['body']['db_error'] = db_error
            
        logger.debug(f"Формируемый ответ: {response_data}")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при проверке здоровья: {str(e)}", exc_info=True)
        response = jsonify({
            "status": False,
            "code": 500,
            "body": {
                "message": "Internal Server Error",
            }
        })
        response.status_code = 500
        return response