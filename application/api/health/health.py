# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, jsonify, request
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_engine, is_database_initialized
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import time
import socket
import psutil
import json
import platform
from datetime import datetime

logger = setup_logger(__name__)

health_bp = Blueprint('health', __name__)

def _log_health_step(step: str, details: str = "", level: str = "info") -> None:
    """Унифицированное логирование шагов проверки здоровья"""
    log_method = getattr(logger, level.lower(), logger.info)
    border = "=" * 50
    log_method(f"\n{border}\nHEALTH CHECK: {step}\n{details}\n{border}")

def _get_system_info() -> dict:
    """Сбор системной информации для логов"""
    try:
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_usage": f"{psutil.cpu_percent()}%",
            "memory_usage": f"{psutil.virtual_memory().percent}%",
            "disk_usage": f"{psutil.disk_usage('/').percent}%",
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            "process_uptime": str(datetime.now() - datetime.fromtimestamp(psutil.Process().create_time()))
        }
    except Exception as e:
        logger.warning(f"Не удалось собрать системную информацию: {str(e)}")
        return {"error": str(e)}

@health_bp.route('/health')
def health_check():
    """
    Расширенная проверка работоспособности сервиса с детальным логированием.
    
    Логирует:
    - Время выполнения каждого этапа проверки
    - Системные метрики (CPU, память, диск)
    - Подробную информацию о состоянии БД
    - Параметры запроса
    - Версии компонентов
    """
    start_time = time.time()
    request_id = f"{time.time():.0f}-{hash(request.remote_addr)}"
    
    try:
        _log_health_step(
            "Начало проверки здоровья",
            f"Request ID: {request_id}\n"
            f"Клиент: {request.remote_addr}\n"
            f"User-Agent: {request.user_agent}"
        )
        
        # Сбор системной информации
        system_info = _get_system_info()
        logger.debug(f"Системная информация:\n{json.dumps(system_info, indent=2)}")
        
        # Проверка конфигурации
        config_check_time = time.time()
        app_version = config.get('version', '0.0.0')
        debug_mode = config.get('app.debug', False)
        
        _log_health_step(
            "Проверка конфигурации",
            f"Версия приложения: {app_version}\n"
            f"Режим отладки: {'ВКЛ' if debug_mode else 'ВЫКЛ'}\n"
            f"Время проверки: {(time.time() - config_check_time) * 1000:.2f} мс"
        )
        
        # Проверка базы данных
        db_check = {
            "status": False,
            "error": None,
            "response_time": None,
            "details": {}
        }
        
        if not is_database_initialized():
            db_check["error"] = "Database not initialized"
            logger.error("База данных не инициализирована")
        else:
            try:
                db_start_time = time.time()
                engine = get_db_engine()
                
                _log_health_step(
                    "Проверка подключения к БД",
                    f"Тип engine: {type(engine).__name__}\n"
                    f"Состояние пула: {engine.pool.status()}"
                )
                
                with engine.connect() as conn:
                    # Проверка соединения
                    test_query_start = time.time()
                    result = conn.execute(text("SELECT 1 as status, version() as db_version"))
                    row = result.fetchone()
                    
                    db_check.update({
                        "status": bool(row),
                        "response_time": time.time() - db_start_time,
                        "details": {
                            "db_version": row.db_version,
                            "query_time": f"{(time.time() - test_query_start) * 1000:.2f} мс"
                        }
                    })
                    
                    _log_health_step(
                        "Тестовый запрос выполнен",
                        f"Версия БД: {row.db_version}\n"
                        f"Время запроса: {db_check['details']['query_time']}\n"
                        f"Общее время проверки БД: {db_check['response_time'] * 1000:.2f} мс"
                    )
                    
            except SQLAlchemyError as db_e:
                db_check["error"] = str(db_e)
                _log_health_step(
                    "Ошибка SQLAlchemy",
                    f"Тип: {type(db_e).__name__}\n"
                    f"Сообщение: {db_check['error']}",
                    "error"
                )
            except Exception as db_e:
                db_check["error"] = str(db_e)
                _log_health_step(
                    "Неожиданная ошибка БД",
                    f"Тип: {type(db_e).__name__}\n"
                    f"Сообщение: {db_check['error']}",
                    "critical"
                )
        
        # Формирование ответа
        response_data = {
            "status": True,
            "code": 200,
            "body": {
                "app_version": app_version,
                "database": db_check["status"],
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        if db_check["error"]:
            response_data["body"]["database"]["error"] = db_check["error"]
        
        total_time = time.time() - start_time
        _log_health_step(
            "Проверка здоровья завершена",
            f"Общее время выполнения: {total_time * 1000:.2f} мс\n"
            f"Статус БД: {'OK' if db_check['status'] else 'ERROR'}\n"
            f"Код ответа: 200"
        )
        
        logger.debug(f"Полный ответ:\n{json.dumps(response_data, indent=2)}")
        return jsonify(response_data), 200
        
    except Exception as e:
        total_time = time.time() - start_time
        _log_health_step(
            "Критическая ошибка",
            f"Тип: {type(e).__name__}\n"
            f"Сообщение: {str(e)}\n"
            f"Время до ошибки: {total_time * 1000:.2f} мс",
            "critical"
        )
        
        response_data = {
            "status": False,
            "code": 500,
            "body": {
                "message": "Internal Server Error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        logger.error(f"Формируемый ответ при ошибке:\n{json.dumps(response_data, indent=2)}")
        return jsonify(response_data), 500