# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from api.jwt.jwt_service import JWTService
from api.auth.auth_local_service import AuthService
from maintenance.logger import setup_logger
import hashlib

logger = setup_logger(__name__)

local_auth_bp = Blueprint('local_auth', __name__)

@local_auth_bp.route('/auth/local/', methods=['POST'])
def local_auth():
    """
    Обработчик аутентификации пользователя через локальную БД.
    Безопасное логирование - конфиденциальные данные только в debug режиме.
    """
    try:
        logger.info("Начало процесса аутентификации")
        
        data = request.get_json()
        if not data:
            logger.warning("Пустой запрос")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Отсутствуют данные запроса"}
            }), 400

        auth_data = data.get('auth')
        if not auth_data:
            logger.error("Отсутствует блок аутентификации")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Не указаны данные аутентификации"}
            }), 400

        login = auth_data.get('login')
        password_hash = auth_data.get('password')
        
        # Только общие сообщения в info
        logger.info(f"Аутентификация пользователя (логин: {login})")
        
        # Детали только для debug
        logger.debug(f"Полные данные запроса: {data}")
        logger.debug(f"Заголовки: {dict(request.headers)}")

        if not login:
            logger.error("Не указан логин")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Логин обязателен"}
            }), 400

        if not password_hash:
            logger.error("Не указан пароль")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Пароль обязателен"}
            }), 400

        user = AuthService.get_user_by_credentials(login)
        if not user:
            logger.warning(f"Пользователь не найден: {login}")
            return jsonify({
                "code": 403,
                "status": False,
                "body": {"message": "Неверные учетные данные"}
            }), 403

        logger.debug(f"Найден пользователь ID: {user.user_id}")
        
        if not AuthService.verify_password(password_hash, user.password_hash):
            logger.warning("Неверный пароль")
            return jsonify({
                "code": 403,
                "status": False,
                "body": {"message": "Неверные учетные данные"}
            }), 403

        logger.info(f"Успешная аутентификация (ID: {user.user_id})")
        
        tokens = JWTService.generate_tokens(user.user_id)
        logger.debug("Токены сгенерированы")

        # Создание сессии
        refresh_token_hash = hashlib.sha256(tokens['refresh_token'].encode()).hexdigest()
        JWTService.create_session(
            user_id=user.user_id,
            access_token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            refresh_token_hash=refresh_token_hash,
            user_agent=request.headers.get('User-Agent', ''),
            ip_address=request.remote_addr or ''
        )

        return jsonify({
            "code": 200,
            "status": True,
            "body": {
                "access_token": tokens['access_token'],
                "refresh_token": tokens['refresh_token'],
                "user_id": user.user_id,
                "expires_in": tokens['expires_in']
            }
        }), 200

    except Exception as e:
        logger.critical(f"Ошибка аутентификации: {type(e).__name__}", exc_info=True)
        return jsonify({
            "code": 500,
            "status": False,
            "body": {"message": "Внутренняя ошибка сервера"}
        }), 500