# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from datetime import datetime
from uuid import uuid4
from maintenance.logger import setup_logger
from maintenance.database_connector import get_db_session
from sqlalchemy import text
from ..jwt.token_generator import JWTGenerator

logger = setup_logger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/local_auth', methods=['POST'])
def local_auth():
    """Аутентификация пользователя по логину/паролю"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        password = data.get('password')
        
        # Проверка наличия обязательных полей
        if not user_id or not password:
            return jsonify({
                "status": False,
                "code": 400,
                "body": {"message": "Требуется user_id и password"}
            }), 400
            
        # Проверка учетных данных в БД
        with get_db_session() as session:
            user = session.execute(
                text("""
                    SELECT id, password_hash FROM users 
                    WHERE login = :user_id AND is_active = TRUE
                """),
                {'user_id': user_id}
            ).fetchone()
            
            if not user:
                return jsonify({
                    "status": False,
                    "code": 401,
                    "body": {"message": "Неверные учетные данные"}
                }), 401
                
            # Здесь должна быть проверка пароля (например, через bcrypt)
            if not _verify_password(password, user.password_hash):
                return jsonify({
                    "status": False,
                    "code": 401,
                    "body": {"message": "Неверные учетные данные"}
                }), 401
                
        # Генерация токенов через сервис
        jwt_gen = JWTGenerator()
        if not jwt_gen.check_user_sessions(user.id):
            return jsonify({
                "status": False,
                "code": 403,
                "body": {"message": "Достигнут лимит активных сессий"}
            }), 403
            
        tokens = jwt_gen.create_tokens(user.id)
        
        return jsonify({
            "status": True,
            "code": 200,
            "body": tokens
        })
        
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {str(e)}")
        return jsonify({
            "status": False,
            "code": 500,
            "body": {"message": "Ошибка сервера"}
        }), 500

def _verify_password(input_password: str, stored_hash: str) -> bool:
    """Валидация пароля (заглушка)"""
    # Реальная реализация должна использовать bcrypt или аналоги
    return input_password == stored_hash  # Только для примера!