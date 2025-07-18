# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from api.jwt.jwt_service import JWTService
from maintenance.logger import setup_logger
import hashlib
from datetime import datetime, timedelta

logger = setup_logger(__name__)

local_auth_bp = Blueprint('local_auth', __name__)

@local_auth_bp.route('/auth/local/', methods=['POST'])
def local_auth():
    """
    Обработчик аутентификации пользователя через локальную БД.
    """
    try:
        logger.info("Начало процесса локальной аутентификации")
        logger.debug(f"Получен запрос с заголовками: {request.headers}")
        
        # Логирование тела запроса (без пароля)
        data = request.get_json()
        if data:
            logged_data = data.copy()
            if 'auth' in logged_data and 'password' in logged_data['auth']:
                logged_data['auth']['password'] = '***FILTERED***'
            logger.debug(f"Тело запроса (фильтрованное): {logged_data}")
        else:
            logger.warning("Получен запрос с пустым телом")

        if not data:
            logger.error("Получены пустые данные запроса")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Отсутствуют данные запроса"}
            }), 400

        auth_data = data.get('auth')
        if not auth_data:
            logger.error("Отсутствует блок 'auth' в запросе. Полученные данные: %s", data)
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Не указаны данные аутентификации"}
            }), 400

        login = auth_data.get('login')
        password_hash = auth_data.get('password')
        
        if not login:
            logger.error("Не указан логин в запросе")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Логин обязателен для заполнения"}
            }), 400

        if not password_hash:
            logger.error("Не указан пароль в запросе для пользователя: %s", login)
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Пароль обязателен для заполнения"}
            }), 400

        logger.info(f"Попытка аутентификации пользователя: {login}")
        user = JWTService.get_user_by_credentials(login)
        
        if not user:
            logger.warning(f"Пользователь не найден в системе: {login}")
            return jsonify({
                "code": 403,
                "status": False,
                "body": {"message": "Неверные учетные данные"}
            }), 403

        logger.debug(f"Найден пользователь с ID: {user.user_id}")
        
        if user.password != password_hash:
            logger.warning(f"Неверный пароль для пользователя: {login}")
            return jsonify({
                "code": 403,
                "status": False,
                "body": {"message": "Неверные учетные данные"}
            }), 403

        logger.info(f"Успешная аутентификация пользователя: {login} (ID: {user.user_id})")
        tokens = JWTService.generate_tokens(user.user_id)
        logger.debug(f"Сгенерированы токены для пользователя ID: {user.user_id}")
        
        # Получаем данные для сессии
        user_agent = request.headers.get('User-Agent', '')
        ip_address = request.remote_addr or ''
        
        # Создаем хеш refresh токена для хранения в БД
        refresh_token_hash = hashlib.sha256(tokens['refresh_token'].encode()).hexdigest()
        
        # Создаем сессию с дополнительными данными
        JWTService.create_session(
            user_id=user.user_id,
            access_token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address
        )
        logger.info(f"Сессия создана для пользователя ID: {user.user_id}")

        response_data = {
            "code": 200,
            "status": True,
            "body": {
                "access_token": tokens['access_token'][:10] + "...",  # Логируем только часть токена
                "refresh_token": tokens['refresh_token'][:10] + "...",
                "user_id": user.user_id,
                "expires_in": tokens['expires_in']
            }
        }
        logger.debug(f"Формирование ответа: {response_data}")
        
        return jsonify(response_data), 200

    except Exception as e:
        logger.critical(f"Критическая ошибка при аутентификации: {str(e)}", exc_info=True)
        return jsonify({
            "code": 500,
            "status": False,
            "body": {"message": "Внутренняя ошибка сервера"}
        }), 500