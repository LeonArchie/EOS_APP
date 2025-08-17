# read_param.py
from flask import Blueprint, jsonify
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

read_bp = Blueprint('read', __name__)

CONFIG_DIR = "configures"

@read_bp.route('config/read/<path:file_path>', methods=['GET'])
def read_parameter(file_path):
    try:
        logger.info(f"Получен запрос на чтение параметра: {file_path}")
        
        # Разделяем путь на имя файла и путь к параметру
        parts = file_path.split('/')
        if len(parts) < 2:
            logger.error("Неверный формат запроса. Ожидается: имя_файла/путь_к_параметру")
            return jsonify({"error": "Неверный формат запроса. Используйте: /read/имя_файла/путь_к_параметру"}), 400
        
        filename = parts[0]
        param_path = parts[1:]
        
        # Проверяем существование файла
        file_full_path = os.path.join(CONFIG_DIR, f"{filename}.json")
        if not os.path.exists(file_full_path):
            logger.error(f"Файл конфигурации не найден: {filename}.json")
            return jsonify({"error": f"Файл конфигурации {filename}.json не найден"}), 404
        
        # Читаем и парсим JSON-файл
        with open(file_full_path, 'r') as f:
            config_data = json.load(f)
        
        # Рекурсивно ищем параметр по пути
        current_value = config_data
        for part in param_path:
            if part not in current_value:
                logger.error(f"Параметр не найден: {'/'.join(param_path)} в файле {filename}.json")
                return jsonify({"error": f"Параметр {'/'.join(param_path)} не найден в файле {filename}.json"}), 404
            current_value = current_value[part]
        
        logger.info(f"Успешно прочитан параметр: {'/'.join(param_path)} из файла {filename}.json")
        return jsonify({
            "file": f"{filename}.json",
            "parameter": '/'.join(param_path),
            "value": current_value
        }), 200
    
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в файле {filename}.json: {str(e)}")
        return jsonify({"error": f"Ошибка формата JSON в файле {filename}.json"}), 500
    except Exception as e:
        logger.error(f"Ошибка при чтении параметра: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500