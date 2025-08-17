from flask import Blueprint, request, jsonify
import os
import json

config_bp = Blueprint('config', __name__)

# Создаем папку configures, если ее нет
CONFIG_DIR = "configures"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

@config_bp.route('/config-create/<name>', methods=['POST'])
def create_config(name):
    try:
        # Получаем JSON из тела запроса
        data = request.get_json()
        
        # Проверяем, что данные есть
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Формируем путь к файлу
        file_path = os.path.join(CONFIG_DIR, f"{name}.json")
        
        # Записываем данные в файл
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        return jsonify({"status": "success", "message": f"Config {name}.json created"}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500