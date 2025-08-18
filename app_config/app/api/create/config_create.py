# config_create.py
from flask import Blueprint, request, jsonify
import os
import json
import logging

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)

CONFIG_DIR = "configures"

@config_bp.route('/config-create/<name>', methods=['POST'])
def create_config(name):
    try:
        logger.info("Получен запрос на создание конфигурации: %s", name)
        
        data = request.get_json()
        if not data:
            logger.warning("Запрос не содержит JSON данных")
            return jsonify({"error": "Не предоставлены JSON данные"}), 400
        
        file_path = os.path.join(CONFIG_DIR, f"{name}.json")
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        logger.info("Конфигурационный файл успешно создан: %s", file_path)
        return jsonify({
            "status": "success",
            "message": f"Конфигурация {name}.json создана"
        }), 201
    
    except Exception as e:
        logger.error("Ошибка при создании конфигурации: %s", str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500