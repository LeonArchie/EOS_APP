# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from flask import Blueprint, request, jsonify
import os
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

create_validate_bp = Blueprint('create_validate', __name__)

VALIDATOR_DIR = "validators"

@create_validate_bp.route('/create-validate/<name>', methods=['POST'])
def create_validator(name):
    try:
        logger.info(f"Получен запрос на создание валидатора: {name}")
        
        data = request.get_json()
        if not data:
            logger.warning("Запрос не содержит JSON данных")
            return jsonify({"error": "Не предоставлены JSON данные"}), 400
        
        # Проверяем, что все значения являются валидными regex-шаблонами
        for param_name, pattern in data.items():
            try:
                re.compile(pattern)
            except re.error as e:
                logger.error(f"Неверный regex-шаблон для параметра '{param_name}': {str(e)}")
                return jsonify({
                    "error": f"Неверный regex-шаблон для параметра '{param_name}'",
                    "details": str(e)
                }), 400
        
        # Создаем директорию validators, если её нет
        os.makedirs(VALIDATOR_DIR, exist_ok=True)
        
        # Создаем файл валидатора
        file_path = os.path.join(VALIDATOR_DIR, f"{name}.json")
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"Файл-валидатор успешно создан: {file_path}")
        return jsonify({
            "status": "success",
            "message": f"Валидатор {name}.json создан",
            "path": file_path
        }), 201
    
    except Exception as e:
        logger.error(f"Ошибка при создании валидатора: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500