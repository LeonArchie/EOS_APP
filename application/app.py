from flask import Flask
from maintenance.logger import setup_logger
from maintenance.read_config import config

logger = setup_logger(__name__)

def create_app():
    """Фабрика для создания Flask-приложения"""
    logger.info("Создание Flask-приложения")
    
    try:
        # Инициализация приложения
        app = Flask(__name__)
        
        # Загрузка конфигурации
        app_config = {
            'SECRET_KEY': config.get('app.flask_key', 'default-secret-key'),
            'VERSION': config.get('version', '0.0.0')
        }
        
        app.config.update(app_config)
        
        logger.info("Конфигурация приложения успешно загружена")
        logger.debug(f"Текущая конфигурация: {app_config}")
        
        # Простая проверочная маршрутизация
        @app.route('/')
        def index():
            logger.debug("Обработка запроса к корневому URL")
            return (
                f"Приложение версии {app.config['VERSION']} "
                f"работает на порту {config.get('app.port', 5000)}"
            )
        
        logger.info("Flask-приложение успешно создано")
        return app
        
    except Exception as e:
        logger.critical(f"ОШИБКА СОЗДАНИЯ ПРИЛОЖЕНИЯ: {str(e)}")
        raise

# Создание экземпляра приложения
try:
    logger.info("Инициализация основного приложения")
    app = create_app()
    logger.info("Приложение готово к работе")
except Exception as e:
    logger.critical(f"НЕУДАЛОСЬ ЗАПУСТИТЬ ПРИЛОЖЕНИЕ: {str(e)}")
    raise

if __name__ == '__main__':
    host = config.get('app.address', '0.0.0.0')
    port = config.get('app.port', 5000)
    logger.info(f"Запуск сервера разработки на {host}:{port}")
    try:
        app.run(host=host, port=port)
        logger.info("Сервер разработки успешно запущен")
    except Exception as e:
        logger.critical(f"ОШИБКА ЗАПУСКА СЕРВЕРА: {str(e)}")
        raise