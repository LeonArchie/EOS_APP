from flask import jsonify
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_engine
from sqlalchemy import text
import logging

logger = setup_logger(__name__)

def init_health_route(app):
    @app.route('/health')
    def health_check():
        logger.debug("Обработка запроса проверки здоровья сервиса")
        try:
            engine = get_db_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                db_available = bool(result)
            
            response = jsonify({
                "status": True,
                "code": 200,
                "body": {
                    "app_version": config.get('version', '0.0.0'),
                    "database_available": db_available
                }
            })
            response.status_code = 200  # Явно устанавливаем код ответа
            return response
            
        except Exception as e:
            logger.error(f"Ошибка при проверке БД: {str(e)}")
            response = jsonify({
                "status": False,
                "code": 500,
                "body": {
                    "message": "Failed"
                }
            })
            response.status_code = 500  # Явно устанавливаем код ответа
            return response