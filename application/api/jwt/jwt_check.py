# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from maintenance.logger import setup_logger
from maintenance.database_connector import get_db_session
from api.jwt.jwt_service import JWTService
import jwt
from datetime import datetime, timezone
from sqlalchemy import text

logger = setup_logger(__name__)

jwt_check_bp = Blueprint('jwt_check', __name__)

@jwt_check_bp.route('/jwt/check', methods=['GET'])
def check_jwt():
    """
    Эндпоинт для проверки валидности JWT токена и возможности его обновления.
    
    Проверяет:
    1. Наличие обязательных заголовков (access-token и user-id)
    2. Валидность токена (срок действия, подпись)
    3. Принадлежность токена указанному пользователю
    4. Наличие токена в блэк-листе
    5. Возможность обновления токена (для истекших токенов)
    
    Возвращает различные статусы в зависимости от результатов проверок.
    """
    try:
        logger.info("Начало обработки запроса проверки JWT токена")
        
        # Получаем необходимые заголовки
        access_token = request.headers.get('access-token')
        user_id = request.headers.get('user-id')
        
        logger.debug(f"Полученные заголовки: access-token={'***' if access_token else 'отсутствует'}, user-id={user_id or 'отсутствует'}")
        
        # Проверяем наличие обязательных заголовков
        if not access_token or not user_id:
            logger.warning("Отсутствуют обязательные заголовки access-token или user-id")
            return jsonify({
                "body": {"message": "Необходимы заголовки access-token и user-id"},
                "code": 400,
                "status": False
            }), 400
        
        try:
            # Декодируем токен без проверки срока действия (чтобы получить payload даже для просроченных токенов)
            logger.debug("Попытка декодирования токена (без проверки срока действия)")
            decoded_token = jwt.decode(
                access_token,
                JWTService._get_public_key_pem(),
                algorithms=['RS256'],
                options={'verify_exp': False}
            )
            logger.debug(f"Декодированный токен: {decoded_token}")
            
            # Проверяем принадлежность токена пользователю
            if str(decoded_token.get('user_id')) != user_id:
                logger.warning(f"Токен не принадлежит пользователю. Ожидался user_id={user_id}, получен {decoded_token.get('user_id')}")
                return jsonify({
                    "body": {
                        "token_valid": False,
                        "refresh": False
                    },
                    "code": 403,
                    "status": True
                }), 403
            
            # Проверяем срок действия токена
            current_time = datetime.now(timezone.utc).timestamp()
            token_exp = decoded_token.get('exp', 0)
            
            logger.debug(f"Текущее время: {current_time}, Время истечения токена: {token_exp}")
            
            if current_time > token_exp:
                logger.info("Токен просрочен, проверка возможности обновления")
                
                # Проверяем наличие токена в блэк-листе
                with get_db_session() as session:
                    result = session.execute(
                        text("""
                            SELECT 1 FROM revoked_tokens 
                            WHERE token_hash = SHA256(:token) AND user_id = :user_id
                        """),
                        {'token': access_token, 'user_id': user_id}
                    ).scalar()
                    
                    if result:
                        logger.warning("Токен находится в блэк-листе, обновление невозможно")
                        return jsonify({
                            "body": {
                                "token_valid": False,
                                "refresh": False
                            },
                            "code": 401,
                            "status": True
                        }), 401
                
                # Проверяем возможность обновления (наличие активной сессии)
                with get_db_session() as session:
                    result = session.execute(
                        text("""
                            SELECT 1 FROM sessions 
                            WHERE user_id = :user_id 
                            AND refresh_token_hash = SHA256(:refresh_token)
                            AND expires_at > NOW()
                        """),
                        {'user_id': user_id, 'refresh_token': access_token}
                    ).scalar()
                    
                    if result:
                        logger.info("Для токена возможен refresh")
                        return jsonify({
                            "body": {
                                "token_valid": False,
                                "refresh": True
                            },
                            "code": 401,
                            "status": True
                        }), 401
                    else:
                        logger.warning("Для токена невозможен refresh (нет активной сессии)")
                        return jsonify({
                            "body": {
                                "token_valid": False,
                                "refresh": False
                            },
                            "code": 401,
                            "status": True
                        }), 401
            
            # Если токен валиден и принадлежит пользователю
            logger.info("Токен валиден и принадлежит пользователю")
            return jsonify({
                "body": {
                    "token_valid": True
                },
                "code": 200,
                "status": True
            }), 200
            
        except jwt.InvalidTokenError as e:
            logger.error(f"Невалидный токен: {str(e)}")
            return jsonify({
                "body": {
                    "token_valid": False,
                    "refresh": False
                },
                "code": 403,
                "status": True
            }), 403
            
    except Exception as e:
        logger.critical(f"Критическая ошибка при проверке токена: {type(e).__name__}: {str(e)}", exc_info=True)
        return jsonify({
            "body": {"message": "Внутренняя ошибка сервера"},
            "code": 500,
            "status": False
        }), 500