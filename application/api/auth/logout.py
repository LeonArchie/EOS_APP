# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from maintenance.logger import setup_logger
from maintenance.database_connector import get_db_session
from sqlalchemy import text

logger = setup_logger(__name__)
logout_bp = Blueprint('auth_logout', __name__, url_prefix='/api/auth')

@logout_bp.route('/logout', methods=['POST'])
def logout():
    """Завершение сессии и отзыв токенов"""
    try:
        access_token = request.headers.get('access-token')
        refresh_token = request.headers.get('refresh-token')
        
        if not access_token or not refresh_token:
            return jsonify({
                "status": False,
                "code": 400,
                "body": {"message": "Требуется access-token и refresh-token"}
            }), 400
            
        # Отзыв токенов
        with get_db_session() as session:
            # Добавление токенов в блэклист
            session.execute(
                text("INSERT INTO revoked_tokens (token) VALUES (:token)"),
                [{'token': access_token}, {'token': refresh_token}]
            )
            
            # Получение session_id из токена (без повторной проверки)
            try:
                payload = jwt.decode(access_token, config.get('app.jwt_key'), algorithms=['HS256'], options={'verify_exp': False})
                session_id = payload['session_id']
                
                # Удаление сессии
                session.execute(
                    text("DELETE FROM active_sessions WHERE session_id = :session_id"),
                    {'session_id': session_id}
                )
                
            except jwt.InvalidTokenError:
                logger.warning("Невалидный токен при выходе, но все равно отозван")
                
            session.commit()
            
        return jsonify({
            "status": True,
            "code": 200,
            "body": {"message": "Сессия завершена"}
        })
        
    except Exception as e:
        logger.error(f"Ошибка выхода из системы: {str(e)}")
        return jsonify({
            "status": False,
            "code": 500,
            "body": {"message": "Ошибка сервера"}
        }), 500