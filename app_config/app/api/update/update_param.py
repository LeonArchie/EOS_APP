# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

# update_param.py
from flask import Blueprint, request, jsonify
import os
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

update_bp = Blueprint('update', __name__)

CONFIG_DIR = "configures"
VALIDATOR_DIR = "validators"

def load_validator(filename):
    """Загружает файл-валидатор с regex-шаблонами"""
    validator_path = os.path.join(VALIDATOR_DIR, f"{filename}.json")
    if not os.path.exists(validator_path):
        logger.warning(f"Файл-валидатор не найден: {filename}.json. Валидация пропущена.")
        return None
    
    with open(validator_path, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Неверный JSON в файле-валидаторе {filename}.json: {str(e)}")
            return None

def validate_parameter(param_name, value, validator):
    """Проверяет значение параметра по regex-шаблону из валидатора"""
    if validator is None:
        logger.warning("Валидатор не загружен. Проверка пропущена.")
        return True
    
    if param_name not in validator:
        logger.warning(f"Шаблон для параметра '{param_name}' не найден в валидаторе. Проверка пропущена.")
        return True
    
    pattern = validator[param_name]
    try:
        if not re.fullmatch(pattern, str(value)):
            logger.error(f"Значение '{value}' не соответствует шаблону '{pattern}' для параметра '{param_name}'")
            return False
        return True
    except re.error as e:
        logger.error(f"Неверный regex-шаблон '{pattern}' для параметра '{param_name}': {str(e)}")
        return False

@update_bp.route('/update', methods=['POST'])
def update_parameter():
    try:
        logger.info("Получен запрос на обновление параметра")
        data = request.get_json()
        if not data:
            logger.warning("Запрос не содержит JSON данных")
            return jsonify({"error": "Не предоставлены JSON данные"}), 400
        
        path = data.get('path')
        value = data.get('value')
        
        if not path or value is None:
            logger.error("Отсутствуют обязательные поля 'path' или 'value'")
            return jsonify({"error": "Необходимы оба поля: 'path' и 'value'"}), 400
        
        # Разделяем путь на имя файла и путь к параметру
        parts = path.split('/')
        if len(parts) < 2:
            logger.error("Неверный формат пути. Ожидается: имя_файла/путь_к_параметру")
            return jsonify({"error": "Неверный формат пути. Используйте: имя_файла/параметр1/параметр2"}), 400
        
        filename = parts[0]
        param_path = parts[1:]
        param_name = param_path[-1]  # Последняя часть - имя параметра
        
        # Загружаем валидатор (может быть None, если файла нет)
        validator = load_validator(filename)
        
        # Проверяем параметр (если валидатор есть и содержит шаблон для параметра)
        if not validate_parameter(param_name, value, validator):
            return jsonify({"error": f"Недопустимое значение для параметра '{param_name}'"}), 400
        
        # Загружаем конфигурационный файл
        file_path = os.path.join(CONFIG_DIR, f"{filename}.json")
        if not os.path.exists(file_path):
            logger.error(f"Конфигурационный файл не найден: {filename}.json")
            return jsonify({"error": f"Конфигурационный файл {filename}.json не найден"}), 404
        
        with open(file_path, 'r') as f:
            config_data = json.load(f)
        
        # Находим место параметра в структуре
        current = config_data
        for part in param_path[:-1]:
            if part not in current:
                logger.error(f"Путь не найден: {'/'.join(param_path)} в файле {filename}.json")
                return jsonify({"error": f"Путь {'/'.join(param_path)} не найден в файле {filename}.json"}), 404
            current = current[part]
        
        # Обновляем параметр
        current[param_path[-1]] = value
        
        # Сохраняем обновленную конфигурацию
        with open(file_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        
        logger.info(f"Успешно обновлен параметр: {'/'.join(param_path)} в файле {filename}.json")
        return jsonify({
            "status": "success",
            "message": f"Параметр {'/'.join(param_path)} обновлен",
            "file": f"{filename}.json",
            "parameter": '/'.join(param_path),
            "value": value,
            "validation": "skipped" if validator is None or param_name not in validator else "performed"
        }), 200
    
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON в конфигурационном файле: {str(e)}")
        return jsonify({"error": "Неверный формат JSON в конфигурационном файле"}), 500
    except Exception as e:
        logger.error(f"Ошибка при обновлении параметра: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500