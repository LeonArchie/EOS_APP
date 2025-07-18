# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import re
import json
from flask import request, jsonify
from pathlib import Path
from maintenance.logger import setup_logger

logger = setup_logger(__name__)

class RequestValidationError(Exception):
    """Кастомная ошибка валидации с типом ошибки"""
    def __init__(self, message, error_type="validation"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)

class RequestValidator:
    """
    Валидатор запросов с расширенным логированием
    """

    _instance = None
    _schema = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RequestValidator, cls).__new__(cls)
            cls._load_schema()
        return cls._instance

    @classmethod
    def _load_schema(cls):
        """Загрузка схемы API с подробным логированием"""
        try:
            schema_path = Path(__file__).parent.parent / 'configurations' / 'api_schema.json'
            logger.debug(f"Попытка загрузки схемы API из {schema_path}")
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                cls._schema = json.load(f)
                logger.debug(f"Содержимое схемы API: {json.dumps(cls._schema, indent=2)}")
            
            # Установка дефолтных значений
            cls._schema.setdefault('open_api', [])
            cls._schema.setdefault('headers_validation', {
                'user-id': '^[a-zA-Z0-9-]{1,36}$',
                'access-token': '^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$'
            })
            
            logger.info("Схема API успешно загружена")
        except FileNotFoundError:
            logger.critical("Файл схемы API не найден")
            cls._schema = {'open_api': []}
        except json.JSONDecodeError as e:
            logger.critical(f"Ошибка парсинга схемы API: {str(e)}")
            cls._schema = {'open_api': []}
        except Exception as e:
            logger.critical(f"Неожиданная ошибка загрузки схемы API: {str(e)}", exc_info=True)
            cls._schema = {'open_api': []}

    def validate_request(self):
        """Основной метод валидации с детальным логированием"""
        try:
            logger.debug(f"Начало валидации запроса: {request.method} {request.path}")
            
            # Пропускаем проверки для open_api
            if request.path in self._schema.get('open_api', []):
                logger.debug(f"Эндпоинт {request.path} в списке open_api, проверка пропущена")
                return None
                
            logger.debug("Проверка заголовков")
            self._validate_headers()
            
            logger.debug("Проверка структуры тела запроса")
            self._validate_body_structure()
            
            logger.debug("Валидация запроса успешно завершена")
            return None
            
        except RequestValidationError as e:
            logger.warning(f"Ошибка валидации (тип: {e.error_type}): {e.message}")
            return self._format_error(e)
        except Exception as e:
            logger.error(f"Внутренняя ошибка валидатора: {str(e)}", exc_info=True)
            return self._format_error(
                RequestValidationError("Внутренняя ошибка сервера", "server_error")
            )

    def _validate_headers(self):
        """Проверка заголовков с логированием"""
        required_headers = ['user-id', 'access-token']
        logger.debug(f"Требуемые заголовки: {required_headers}")
        
        for header in required_headers:
            if header not in request.headers:
                logger.warning(f"Отсутствует обязательный заголовок: {header}")
                raise RequestValidationError(
                    "Неверные заголовки запроса",
                    "invalid_headers"
                )
                
            if not request.headers[header]:
                logger.warning(f"Пустое значение заголовка: {header}")
                raise RequestValidationError(
                    "Неверные заголовки запроса",
                    "invalid_headers"
                )
            
            pattern = self._schema['headers_validation'].get(header)
            if pattern:
                logger.debug(f"Проверка заголовка {header} по паттерну: {pattern}")
                if not re.fullmatch(pattern, request.headers[header]):
                    logger.warning(f"Несоответствие паттерну для заголовка {header}: {request.headers[header]}")
                    raise RequestValidationError(
                        "Неверные заголовки запроса",
                        "invalid_headers"
                    )

    def _validate_body_structure(self):
        """Валидация тела запроса с логированием"""
        endpoint_schema = self._schema.get(request.path)
        if not endpoint_schema:
            logger.debug(f"Спецификация для {request.path} не найдена, проверка тела пропущена")
            return

        try:
            data = request.get_json(silent=True) or {}
            logger.debug(f"Тело запроса: {json.dumps(data, indent=2)}")
            
            if isinstance(endpoint_schema, list) and endpoint_schema == []:
                if data:
                    logger.warning("Тело запроса должно быть пустым, но получено: {data}")
                    raise RequestValidationError(
                        "Тело запроса должно быть пустым",
                        "invalid_body"
                    )
                logger.debug("Проверка пустого тела выполнена успешно")
                return

            logger.debug(f"Проверка структуры по схеме: {json.dumps(endpoint_schema, indent=2)}")
            self._validate_nested(data, endpoint_schema)
            
        except json.JSONDecodeError:
            logger.warning("Невалидный JSON в теле запроса")
            raise RequestValidationError(
                "Неверный формат JSON",
                "invalid_json"
            )

    def _validate_nested(self, data, schema, path=""):
        """Рекурсивная валидация с логированием пути"""
        for field, pattern in schema.items():
            current_path = f"{path}.{field}" if path else field
            logger.debug(f"Проверка поля: {current_path}")
            
            if field not in data:
                logger.warning(f"Отсутствует обязательное поле: {current_path}")
                raise RequestValidationError(
                    "Неверный запрос",
                    "invalid_body"
                )
                
            if isinstance(pattern, dict):
                logger.debug(f"Вложенная структура для поля: {current_path}")
                if not isinstance(data[field], dict):
                    logger.warning(f"Ожидался словарь для поля {current_path}, получено: {type(data[field])}")
                    raise RequestValidationError(
                        "Неверный запрос",
                        "invalid_body"
                    )
                self._validate_nested(data[field], pattern, current_path)
            else:
                logger.debug(f"Проверка значения поля {current_path} по паттерну: {pattern}")
                if not re.fullmatch(pattern, str(data[field])):
                    logger.warning(f"Несоответствие паттерну для поля {current_path}: {data[field]}")
                    raise RequestValidationError(
                        "Неверный запрос",
                        "invalid_body"
                    )

    def _format_error(self, error):
        """Форматирование ошибки с логированием"""
        error_types = {
            "invalid_headers": (400, "Неверные заголовки запроса"),
            "invalid_body": (400, "Неверный запрос"),
            "invalid_json": (400, "Неверный формат данных"),
            "server_error": (500, "Внутренняя ошибка сервера")
        }
        
        code, message = error_types.get(error.error_type, (400, "Неверный запрос"))
        logger.debug(f"Формирование ответа с ошибкой: код={code}, тип={error.error_type}")
        
        return jsonify({
            "code": code,
            "status": False,
            "body": {"message": message}
        }), code

    def init_app(self, app):
        """Инициализация валидатора с логированием"""
        logger.info("Инициализация RequestValidator в приложении")
        
        @app.before_request
        def before_request_handler():
            logger.debug(f"Обработка запроса: {request.method} {request.path}")
            if error_response := self.validate_request():
                return error_response

        @app.errorhandler(404)
        def handle_not_found(e):
            logger.warning(f"404 Not Found: {request.method} {request.path}")
            return jsonify({
                "code": 404,
                "status": False,
                "body": {"message": "Метод не поддерживается"}
            }), 404

        @app.errorhandler(500)
        def handle_server_error(e):
            logger.error(f"500 Internal Server Error: {str(e)}", exc_info=True)
            return jsonify({
                "code": 500,
                "status": False,
                "body": {"message": "Внутренняя ошибка сервера"}
            }), 500