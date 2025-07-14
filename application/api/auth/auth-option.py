# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import jsonify
from maintenance.read_config import config
from maintenance.logger import setup_logger

def init_auth_option_route(app):
    """Инициализация эндпоинта /auth-option"""
    @app.route('/auth-option', methods=['GET'])
    def auth_option():
        try:
            # Получаем массив auth из конфигурации
            auth_methods = config.get('auth', {})
            
            # Фильтруем только активные методы
            active_methods = [
                method for method in auth_methods.values() 
                if isinstance(method, dict) and method.get('active', False)
            ]
            
            response = {
                "body": active_methods,
                "code": 200,
                "status": True
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке /auth-option: {str(e)}")
            return jsonify({
                "body": [],
                "code": 500,
                "status": False,
            }), 500