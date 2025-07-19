# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
from api.jwt.jwt_service import JWTService
from api.auth.auth_local_service import AuthService
from maintenance.logger import setup_logger
import hashlib
import json

logger = setup_logger(__name__)

local_auth_bp = Blueprint('local_auth', __name__)

@local_auth_bp.route('/auth/local/', methods=['POST'])
def local_auth():
    """Обработчик аутентификации пользователя через локальную БД."""
    try:
        # Логирование начала процесса аутентификации с IP
        client_ip = request.headers.get('X-Real-Ip', request.remote_addr or 'unknown')
        logger.info(f"[Auth Start] Начало процесса аутентификации. IP: {client_ip}, User-Agent: {request.headers.get('User-Agent', 'unknown')}")
        
        # Получение и валидация JSON данных
        data = request.get_json()
        if not data:
            logger.warning("[Validation] Пустой JSON запрос. Отсутствуют данные.")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Отсутствуют данные запроса"}
            }), 400

        logger.debug(f"[Request Data] Получены данные запроса: {json.dumps(data, ensure_ascii=False)}")

        # Проверка наличия блока аутентификации
        auth_data = data.get('auth')
        if not auth_data:
            logger.error("[Validation] Отсутствует обязательный блок 'auth' в запросе.")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Не указаны данные аутентификации"}
            }), 400

        # Извлечение логина и пароля
        login = auth_data.get('login')
        password_hash = auth_data.get('password')
        
        logger.info(f"[Auth Attempt] Попытка аутентификации для логина: '{login}'")

        # Валидация логина
        if not login:
            logger.error("[Validation] Логин не указан или пуст.")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Логин обязателен"}
            }), 400

        # Валидация пароля
        if not password_hash:
            logger.error("[Validation] Хеш пароля не указан или пуст.")
            return jsonify({
                "code": 400,
                "status": False,
                "body": {"message": "Пароль обязателен"}
            }), 400

        # Поиск пользователя в базе данных
        logger.debug(f"[DB Query] Поиск пользователя с логином: '{login}'")
        user = AuthService.get_user_by_credentials(login)
        
        if not user:
            logger.warning(f"[Auth Failure] Пользователь с логином '{login}' не найден в системе.")
            return jsonify({
                "code": 403,
                "status": False,
                "body": {"message": "Неверные учетные данные"}
            }), 403

        logger.debug(f"[User Found] Найден пользователь: ID={user.user_id}, Login={login}")

        # Проверка пароля
        logger.debug("[Password Verify] Начало проверки хеша пароля")
        if not AuthService.verify_password(password_hash, user.password_hash):
            logger.warning(f"[Auth Failure] Неверный пароль для пользователя '{login}' (ID: {user.user_id})")
            return jsonify({
                "code": 403,
                "status": False,
                "body": {"message": "Неверные учетные данные"}
            }), 403

        logger.info(f"[Auth Success] Успешная аутентификация пользователя (ID: {user.user_id}, Login: {login})")
        
        # Генерация JWT токенов
        logger.debug("[Token Generation] Генерация JWT токенов")
        tokens = JWTService.generate_tokens(user.user_id)
        logger.debug(f"[Tokens Generated] Токены сгенерированы. Срок действия: {tokens['expires_in']} сек.")

        # Подготовка данных для сессии
        ip_address = request.headers.get('X-Real-Ip', request.remote_addr or 'unknown')
        user_agent = request.headers.get('User-Agent', 'unknown')
        refresh_token_hash = hashlib.sha256(tokens['refresh_token'].encode()).hexdigest()
        
        logger.debug(f"[Session Prep] Подготовка сессии: IP={ip_address}, User-Agent={user_agent}")

        # Создание сессии
        logger.debug("[Session Create] Создание сессии в базе данных")
        session_id = JWTService.create_session(
            user_id=user.user_id,
            access_token=tokens['access_token'],
            refresh_token=tokens['refresh_token'],
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address
        )

        logger.info(f"[Session Created] Сессия создана успешно. SessionID: {session_id}, UserID: {user.user_id}")

        # Формирование успешного ответа
        response_data = {
            "code": 200,
            "status": True,
            "body": {
                "access_token": tokens['access_token'],
                "refresh_token": tokens['refresh_token'],
                "session_id": session_id,
                "user_id": user.user_id,
                "expires_in": tokens['expires_in']
            }
        }
        
        logger.debug(f"[Response] Формирование ответа: {json.dumps(response_data, ensure_ascii=False)}")
        return jsonify(response_data), 200

    except Exception as e:
        logger.critical(f"[Critical Error] Ошибка аутентификации: {type(e).__name__}: {str(e)}", exc_info=True)
        return jsonify({
            "code": 500,
            "status": False,
            "body": {"message": "Внутренняя ошибка сервера"}
        }), 500