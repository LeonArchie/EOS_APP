from flask import Flask
from maintenance.logger import setup_logger
from maintenance.read_config import config
from maintenance.database_connector import get_db_engine
from sqlalchemy import text
import time
import logging

logger = setup_logger(__name__)

def wait_for_database_connection():
    """
    Ожидание успешного подключения к базе данных с параметрами из конфига
    """
    max_retries = config.get('db.max_retries', 5)
    retry_delay = config.get('db.retry_delay', 5)
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.info(f"Попытка подключения к базе данных ({retry_count + 1}/{max_retries})")
            engine = get_db_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Подключение к базе данных успешно установлено")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
    
    logger.critical(f"Не удалось установить подключение к базе данных после {max_retries} попыток")
    return False

def create_app():
    """
    Фабрика для создания Flask-приложения с проверкой подключения к БД
    """
    logger.info("Создание Flask-приложения")
    
    try:
        # Проверка подключения к БД перед инициализацией приложения
        if not wait_for_database_connection():
            raise RuntimeError("Не удалось подключиться к базе данных")

        # Инициализация приложения
        app = Flask(__name__)
        
        # Загрузка конфигурации
        app_config = {
            'SECRET_KEY': config.get('app.flask_key', 'default-secret-key'),
            'VERSION': config.get('version', '0.0.0'),
            'SQLALCHEMY_DATABASE_URI': f"postgresql://{config.get('db.user')}:{config.get('db.password')}@{config.get('db.master_host')}:{config.get('db.master_port')}/{config.get('db.database')}",
            'SQLALCHEMY_TRACK_MODIFICATIONS': False
        }
        
        app.config.update(app_config)
        
        logger.info("Конфигурация приложения успешно загружена")
        
        @app.route('/')
        def index():
            logger.debug("Обработка запроса к корневому URL")
            try:
                engine = get_db_engine()
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    db_status = "База данных доступна" if result else "Ошибка БД"
                
                return (
                    f"Приложение версии {app.config['VERSION']}<br>"
                    f"Работает на порту {config.get('app.port', 5000)}<br>"
                    f"Статус БД: {db_status}<br>"
                    f"Параметры подключения: {config.get('db.max_retries')} попыток, задержка {config.get('db.retry_delay')}с"
                )
            except Exception as e:
                logger.error(f"Ошибка при проверке БД: {str(e)}")
                return "Ошибка подключения к базе данных", 500
        
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