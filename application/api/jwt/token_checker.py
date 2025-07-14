# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from maintenance.logger import setup_logger
from maintenance.database_connector import get_db_session
from sqlalchemy import text
import jwt
from maintenance.read_config import config

logger = setup_logger(__name__)
check_bp = Blueprint('jwt_check', __name__, url_prefix='/api/jwt')

@check_bp.route('/check', methods=['POST'])
def check_token():
    """Проверка валидности токена"""
    try:
        access_token = request.headers.get('access-token')
        if not access_token:
            return jsonify({
                "status": False,
                "code": 401,
                "body": {"message": "Требуется access-token"}
            }), 401
            
        # Проверка подписи и срока действия
        try:
            payload = jwt.decode(access_token, config.get('app.jwt_key'), algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({
                "status": False,
                "code": 401,
                "body": {"message": "Токен просрочен"}
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "status": False,
                "code": 401,
                "body": {"message": "Невалидный токен"}
            }), 401
            
        # Проверка отзыва токена
        with get_db_session() as session:
            revoked = session.execute(
                text("SELECT 1 FROM revoked_tokens WHERE token = :token"),
                {'token': access_token}
            ).fetchone()
            
            if revoked:
                return jsonify({
                    "status": False,
                    "code": 401,
                    "body": {"message": "Токен отозван"}
                }), 401
                
        return jsonify({
            "status": True,
            "code": 200,
            "body": {
                "user_id": payload['user_id'],
                "session_id": payload['session_id']
            }
        })
        
    except Exception as e:
        logger.error(f"Ошибка проверки токена: {str(e)}")
        return jsonify({
            "status": False,
            "code": 500,
            "body": {"message": "Ошибка сервера"}
        }), 500