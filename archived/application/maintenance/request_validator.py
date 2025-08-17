# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import re
import json
from flask import request, jsonify
from pathlib import Path
from maintenance.logger import setup_logger
from typing import Dict, Any, Optional, Union
from api.jwt.jwt_service import JWTService
from maintenance.database_connector import get_db_session
from sqlalchemy import text
import jwt
from datetime import datetime, timezone

logger = setup_logger(__name__)

class RequestValidationError(Exception):
    """Кастомная ошибка валидации с типом ошибки"""
    def __init__(self, message: str, error_type: str = "validation"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)
        logger.debug(f"Создана ошибка валидации: тип={error_type}, сообщение={message}")

class RequestValidator:
    """
    Валидатор запросов с расширенным логированием всех этапов работы
    """

    _instance = None
    _schema = None

    def __new__(cls):
        if cls._instance is None:
            logger.info("Инициализация нового экземпляра RequestValidator")
            cls._instance = super(RequestValidator, cls).__new__(cls)
            cls._load_schema()
        else:
            logger.debug("Использование существующего экземпляра RequestValidator")
        return cls._instance

    @classmethod
    def _load_schema(cls):
        """Загрузка и валидация схемы API с максимально подробным логированием"""
        try:
            schema_path = Path(__file__).parent.parent / 'configurations' / 'api_schema.json'
            logger.info(f"Начало загрузки схемы API из файла: {schema_path.absolute()}")

            if not schema_path.exists():
                logger.critical(f"Файл схемы не существует по пути: {schema_path.absolute()}")
                raise FileNotFoundError(f"API schema file not found at {schema_path}")

            with open(schema_path, 'r', encoding='utf-8') as f:
                logger.debug("Чтение содержимого файла схемы")
                file_content = f.read()
                logger.debug(f"Сырое содержимое файла:\n{file_content}")
                
                cls._schema = json.loads(file_content)
                logger.info(f"Схема API успешно загружена. Количество эндпоинтов: {len(cls._schema)}")

            # Логирование структуры схемы
            logger.debug("Детали загруженной схемы API:")
            for endpoint, rules in cls._schema.items():
                logger.debug(f"Эндпоинт: {endpoint}")
                if isinstance(rules, dict):
                    logger.debug(f"  Правила валидации: {json.dumps(rules, indent=2)}")
                else:
                    logger.debug(f"  Тип правил: {type(rules).__name__}")

            # Установка дефолтных значений
            logger.debug("Проверка и установка значений по умолчанию")
            cls._schema.setdefault('open_api', [])
            cls._schema.setdefault('headers_validation', {
                'user-id': '^[a-zA-Z0-9-]{1,36}$',
                'access-token': '^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$'
            })
            
            logger.info("Инициализация схемы API завершена успешно")

        except FileNotFoundError as e:
            logger.critical("Файл схемы API не найден. Будет использована пустая схема", exc_info=True)
            cls._schema = {'open_api': []}
        except json.JSONDecodeError as e:
            logger.critical(f"Ошибка парсинга JSON в схеме API. Позиция ошибки: {e.pos}. Текст: {e.doc}", exc_info=True)
            cls._schema = {'open_api': []}
        except Exception as e:
            logger.critical(f"Критическая ошибка при загрузке схемы API: {type(e).__name__}: {str(e)}", exc_info=True)
            cls._schema = {'open_api': []}

    def _validate_jwt_token(self, access_token: str, user_id: str) -> bool:
        """
        Валидация JWT токена с проверкой:
        1. Валидности подписи
        2. Срока действия
        3. Принадлежности пользователю
        4. Отсутствия в блеклисте
        
        Параметры:
            access_token: JWT токен
            user_id: Идентификатор пользователя
            
        Возвращает:
            bool: True если токен валиден, False если нет
        """
        try:
            logger.debug(f"Начало валидации JWT токена для user_id: {user_id}")
            
            # Декодируем токен без проверки срока действия (чтобы получить payload даже для просроченных токенов)
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
                return False
            
            # Проверяем срок действия токена
            current_time = datetime.now(timezone.utc).timestamp()
            token_exp = decoded_token.get('exp', 0)
            
            if current_time > token_exp:
                logger.info("Токен просрочен, проверка блеклиста")
                return False
            
            # Проверяем наличие токена в блеклисте
            with get_db_session() as session:
                result = session.execute(
                    text("""
                        SELECT 1 FROM revoked_tokens 
                        WHERE token_hash = SHA256(:token) AND user_id = :user_id
                    """),
                    {'token': access_token, 'user_id': user_id}
                ).scalar()
                
                if result:
                    logger.warning("Токен находится в блеклисте")
                    return False
            
            logger.info("JWT токен успешно прошел валидацию")
            return True
            
        except jwt.InvalidTokenError as e:
            logger.error(f"Невалидный токен: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при валидации токена: {str(e)}", exc_info=True)
            return False

    def validate_request(self) -> Optional[Any]:
        """
        Основной метод валидации с детальным логированием всех этапов
        
        Возвращает:
            Optional[Any]: Ответ с ошибкой или None если валидация успешна
        """
        try:
            logger.info(f"Начало валидации {request.method} запроса к {request.path}")
            logger.debug(f"Заголовки запроса:\n{json.dumps(dict(request.headers), indent=2)}")
            logger.debug(f"Параметры запроса: {request.args}")
            logger.debug(f"Данные формы: {request.form}")
            
            # Пропускаем проверки для open_api
            if request.path in self._schema.get('open_api', []):
                logger.info(f"Эндпоинт {request.path} находится в open_api, валидация пропущена")
                return None
                
            # Проверяем наличие спецификации для эндпоинта
            if request.path not in self._schema:
                logger.warning(f"Эндпоинт {request.path} не найден в схеме API")
                raise RequestValidationError(
                    "Эндпоинт не поддерживается",
                    "invalid_endpoint"
                )
                
            logger.info("Начало валидации заголовков")
            self._validate_headers()
            
            # Дополнительная валидация JWT токена
            access_token = request.headers.get('access-token')
            user_id = request.headers.get('user-id')
            
            if access_token and user_id:
                logger.debug("Начало валидации JWT токена")
                if not self._validate_jwt_token(access_token, user_id):
                    logger.warning("JWT токен не прошел валидацию")
                    raise RequestValidationError(
                        "Неверный или просроченный токен",
                        "invalid_token"
                    )
                logger.info("JWT токен успешно прошел валидацию")
            else:
                logger.warning("Отсутствуют обязательные заголовки для JWT валидации")
                raise RequestValidationError(
                    "Неверные заголовки запроса",
                    "invalid_headers"
                )
            
            logger.info("Начало валидации тела запроса")
            self._validate_body_structure()
            
            logger.info(f"Валидация запроса {request.method} {request.path} успешно завершена")
            return None
            
        except RequestValidationError as e:
            logger.warning(f"Ошибка валидации запроса. Тип: {e.error_type}. Сообщение: {e.message}")
            logger.debug(f"Стек ошибки валидации:\n{str(e)}", exc_info=True)
            return self._format_error(e)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при валидации запроса: {type(e).__name__}: {str(e)}", exc_info=True)
            return self._format_error(
                RequestValidationError("Внутренняя ошибка сервера", "server_error")
            )

    def _validate_headers(self):
        """Детальная проверка заголовков с полным логированием"""
        required_headers = ['user-id', 'access-token']
        logger.info(f"Проверка обязательных заголовков: {required_headers}")
        
        for header in required_headers:
            logger.debug(f"Проверка заголовка: {header}")
            
            if header not in request.headers:
                logger.warning(f"Отсутствует обязательный заголовок: {header}")
                logger.debug(f"Полученные заголовки: {list(request.headers.keys())}")
                raise RequestValidationError(
                    "Неверные заголовки запроса",
                    "invalid_headers"
                )
                
            header_value = request.headers[header]
            if not header_value:
                logger.warning(f"Пустое значение для заголовка {header}")
                raise RequestValidationError(
                    "Неверные заголовки запроса",
                    "invalid_headers"
                )
            
            pattern = self._schema['headers_validation'].get(header)
            if pattern:
                logger.debug(f"Применение regex паттерна для заголовка {header}: {pattern}")
                if not re.fullmatch(pattern, header_value):
                    logger.warning(
                        f"Значение заголовка {header} не соответствует паттерну. "
                        f"Значение: '{header_value}', паттерн: '{pattern}'"
                    )
                    raise RequestValidationError(
                        "Неверные заголовки запроса",
                        "invalid_headers"
                    )
            else:
                logger.debug(f"Паттерн для заголовка {header} не найден, проверка пропущена")

        logger.info("Проверка заголовков завершена успешно")

    def _validate_body_structure(self):
        """Валидация тела запроса с максимальной детализацией"""
        endpoint_schema = self._schema.get(request.path)
        
        if endpoint_schema is None:
            logger.warning(f"Спецификация для {request.path} не найдена. Запрос отклонен.")
            raise RequestValidationError(
                "Эндпоинт не поддерживается",
                "invalid_endpoint"
            )

        logger.debug(f"Найдена схема валидации для {request.path}: {json.dumps(endpoint_schema, indent=2)}")

        try:
            data = request.get_json(silent=True) or {}
            logger.debug(f"Полученное тело запроса (JSON):\n{json.dumps(data, indent=2)}")
            
            if isinstance(endpoint_schema, list) and endpoint_schema == []:
                if data:
                    logger.warning(f"Тело запроса должно быть пустым, но получено: {json.dumps(data)}")
                    raise RequestValidationError(
                        "Тело запроса должно быть пустым",
                        "invalid_body"
                    )
                logger.info("Проверка пустого тела выполнена успешно")
                return

            logger.info(f"Начало глубокой валидации тела запроса по схеме")
            self._validate_nested(data, endpoint_schema)
            logger.info("Валидация тела запроса завершена успешно")
            
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка декодирования JSON: {str(e)}")
            logger.debug(f"Сырое тело запроса: {request.data.decode('utf-8', errors='replace')}")
            raise RequestValidationError(
                "Неверный формат JSON",
                "invalid_json"
            )

    def _validate_nested(self, data: Dict, schema: Dict, path: str = "") -> None:
        """Рекурсивная валидация с детальным логированием структуры"""
        logger.debug(f"Валидация вложенной структуры по пути: '{path}'")
        
        for field, pattern in schema.items():
            current_path = f"{path}.{field}" if path else field
            logger.debug(f"Проверка поля: {current_path}")
            
            if field not in data:
                logger.warning(f"Обязательное поле отсутствует: {current_path}")
                logger.debug(f"Доступные поля: {list(data.keys())}")
                raise RequestValidationError(
                    "Неверный запрос",
                    "invalid_body"
                )
                
            field_value = data[field]
            logger.debug(f"Значение поля {current_path}: {field_value} (тип: {type(field_value).__name__})")

            if isinstance(pattern, dict):
                logger.debug(f"Обнаружена вложенная схема для поля {current_path}")
                if not isinstance(field_value, dict):
                    logger.warning(
                        f"Ожидался словарь для поля {current_path}, "
                        f"получен {type(field_value).__name__}: {field_value}"
                    )
                    raise RequestValidationError(
                        "Неверный запрос",
                        "invalid_body"
                    )
                self._validate_nested(field_value, pattern, current_path)
            else:
                logger.debug(f"Проверка значения поля {current_path} по паттерну: {pattern}")
                str_value = str(field_value)
                if not re.fullmatch(pattern, str_value):
                    logger.warning(
                        f"Значение поля {current_path} не соответствует паттерну. "
                        f"Значение: '{str_value}', паттерн: '{pattern}'"
                    )
                    raise RequestValidationError(
                        "Неверный запрос",
                        "invalid_body"
                    )

    def _format_error(self, error: RequestValidationError) -> Any:
        """
        Форматирование ошибки с детальным логированием
        
        Параметры:
            error (RequestValidationError): Ошибка валидации
            
        Возвращает:
            Any: Сформированный ответ Flask
        """
        error_types = {
            "invalid_headers": (400, "Неверные заголовки запроса"),
            "invalid_body": (400, "Неверный запрос"),
            "invalid_json": (400, "Неверный формат данных"),
            "invalid_endpoint": (404, "Эндпоинт не поддерживается"),
            "server_error": (500, "Внутренняя ошибка сервера"),
            "invalid_token": (401, "Неверный или просроченный токен")
        }
        
        code, message = error_types.get(error.error_type, (400, "Неверный запрос"))
        logger.info(f"Формирование ответа с ошибкой. Код: {code}, тип: {error.error_type}, сообщение: {message}")
        
        response_data = {
            "code": code,
            "status": False,
            "body": {"message": message}
        }
        
        logger.debug(f"Полный ответ об ошибке:\n{json.dumps(response_data, indent=2)}")
        return jsonify(response_data), code

    def init_app(self, app) -> None:
        """
        Инициализация валидатора в приложении Flask
        
        Параметры:
            app (Flask): Экземпляр Flask приложения
        """
        logger.info("Начало инициализации RequestValidator в Flask приложении")

        @app.before_request
        def before_request_handler():
            """Глобальный обработчик перед запросом"""
            logger.info(f"Обработка входящего запроса: {request.method} {request.path}")
            logger.debug(f"Полные детали запроса:\n"
                        f"Method: {request.method}\n"
                        f"Path: {request.path}\n"
                        f"Headers: {dict(request.headers)}\n"
                        f"Args: {request.args}\n"
                        f"Form: {request.form}\n"
                        f"JSON: {request.get_json(silent=True)}")
            
            if error_response := self.validate_request():
                logger.info("Запрос не прошел валидацию, возврат ошибки")
                return error_response
            logger.debug("Запрос успешно прошел валидацию")

        @app.errorhandler(404)
        def handle_not_found(e):
            """Обработчик 404 ошибок"""
            logger.warning(f"404 Not Found: {request.method} {request.path}")
            logger.debug(f"Детали 404 ошибки: {str(e)}")
            return jsonify({
                "code": 404,
                "status": False,
                "body": {"message": "Метод не поддерживается"}
            }), 404

        @app.errorhandler(500)
        def handle_server_error(e):
            """Обработчик 500 ошибок"""
            logger.error(f"500 Internal Server Error в запросе {request.method} {request.path}")
            logger.critical(f"Детали 500 ошибки: {type(e).__name__}: {str(e)}", exc_info=True)
            return jsonify({
                "code": 500,
                "status": False,
                "body": {"message": "Внутренняя ошибка сервера"}
            }), 500

        logger.info("RequestValidator успешно инициализирован в Flask приложении")