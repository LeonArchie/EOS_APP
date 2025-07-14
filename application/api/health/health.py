# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, jsonify
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_engine
from sqlalchemy import text

logger = setup_logger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/health')
def health_check():
    logger.debug("Обработка запроса проверки здоровья сервиса")
    try:
        try:
            engine = get_db_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                db_available = bool(result)
        except Exception as db_e:
            logger.error(f"Ошибка при проверке БД: {str(db_e)}", exc_info=True)
            db_available = False
        
        response = jsonify({
            "status": True,
            "code": 200,
            "body": {
                "app_version": config.get('version', '0.0.0'),
                "database_available": db_available
            }
        })
        response.status_code = 200
        return response
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении health check: {str(e)}", exc_info=True)
        response = jsonify({
            "status": False,
            "code": 500,
            "body": {
                "message": "Internal Server Error"
            }
        })
        response.status_code = 500
        return response