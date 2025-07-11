# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import logging
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from maintenance.read_config import config
from maintenance.logger import setup_logger

# Настройка логгеров
logger = setup_logger(__name__)
error_logger = logging.getLogger(f"{__name__}.errors")
error_logger.setLevel(logging.ERROR)

# Конфигурация базы данных из config.json
DB_CONFIG = {
    'host': config.get('db.master_host'),
    'port': config.get('db.master_port'),
    'database': config.get('db.database'),
    'user': config.get('db.user'),
    'password': config.get('db.password'),
    'pool_size': config.get('db.pool_size', 5),
    'max_overflow': config.get('db.max_overflow', 10),
    'pool_timeout': config.get('db.pool_timeout', 30),
    'pool_recycle': config.get('db.pool_recycle', 3600),
    'pool_pre_ping': config.get('db.pool_pre_ping', False),
    'pool_use_lifo': config.get('db.pool_use_lifo', False),
    'replication': config.get('db.replication', 'false'),
    'replica_host': config.get('db.replica_host', ''),
    'replica_port': config.get('db.replica_port', 5432),
    'max_retries': config.get('db.max_retries', 5),
    'retry_delay': config.get('db.retry_delay', 5)
}

# Глобальные переменные для хранения состояния подключения
engine = None
SessionLocal = None
Base = None

def initialize_database():
    """
    Инициализация пула подключений к базе данных
    """
    global engine, SessionLocal, Base
    
    try:
        logger.info("Инициализация подключения к базе данных")
        logger.info(f"Параметры подключения: host={DB_CONFIG['host']}, port={DB_CONFIG['port']}, db={DB_CONFIG['database']}")
        
        # Формирование строки подключения
        connection_string = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )
        
        logger.info("Создание движка SQLAlchemy с пулом подключений")
        engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=DB_CONFIG['pool_size'],
            max_overflow=DB_CONFIG['max_overflow'],
            pool_timeout=DB_CONFIG['pool_timeout'],
            pool_recycle=DB_CONFIG['pool_recycle'],
            pool_pre_ping=DB_CONFIG['pool_pre_ping'],
            pool_use_lifo=DB_CONFIG['pool_use_lifo'],
            echo=False
        )
        
        # Тестовое подключение к базе данных
        with engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
        logger.info("Тестовое подключение к базе данных выполнено успешно")
        
        # Настройка фабрики сессий
        SessionLocal = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=engine))
        
        Base = declarative_base()
        
        logger.info("Пул подключений успешно инициализирован")
        logger.info(f"Настройки пула: размер={DB_CONFIG['pool_size']}, max_overflow={DB_CONFIG['max_overflow']}, "
                   f"timeout={DB_CONFIG['pool_timeout']}s, recycle={DB_CONFIG['pool_recycle']}s, "
                   f"pre_ping={DB_CONFIG['pool_pre_ping']}, lifo={DB_CONFIG['pool_use_lifo']}")
        
        if DB_CONFIG['replication'] == 'true' and DB_CONFIG['replica_host']:
            logger.info(f"Настроена репликация: реплика на {DB_CONFIG['replica_host']}:{DB_CONFIG['replica_port']}")
        
    except Exception as e:
        error_msg = f"Критическая ошибка при инициализации базы данных: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

@contextmanager
def get_db_session():
    """
    Контекстный менеджер для работы с сессиями базы данных
    """
    session = None
    try:
        logger.info("Получение сессии из пула подключений")
        session = SessionLocal()
        yield session
        session.commit()
        logger.info("Изменения успешно зафиксированы в базе данных")
    except Exception as e:
        if session:
            session.rollback()
            logger.info("Выполнен откат изменений из-за ошибки")
        
        error_msg = f"Ошибка при работе с базой данных: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        logger.error(error_msg)
        raise
    finally:
        if session:
            session.close()
            logger.info("Сессия закрыта и возвращена в пул")

def get_db_engine():
    """
    Получение движка базы данных
    """
    if engine is None:
        error_msg = "Движок базы данных не инициализирован"
        error_logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("Запрос движка базы данных")
    return engine

def init_db():
    """
    Инициализация таблиц в базе данных
    """
    try:
        logger.info("Создание таблиц в базе данных")
        if Base is not None:
            Base.metadata.create_all(bind=engine)
            logger.info("Таблицы успешно созданы")
        else:
            error_msg = "Базовый класс моделей не инициализирован"
            error_logger.error(error_msg)
            raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Ошибка при создании таблиц: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        logger.error(error_msg)
        raise

def close_connection_pool():
    """
    Закрытие всех подключений в пуле
    """
    global engine
    if engine:
        try:
            logger.info("Закрытие пула подключений")
            engine.dispose()
            logger.info("Пул подключений успешно закрыт")
        except Exception as e:
            error_msg = f"Ошибка при закрытии пула: {str(e)}"
            error_logger.error(error_msg, exc_info=True)
            logger.error(error_msg)
            raise

# Инициализация при импорте модуля
try:
    initialize_database()
    logger.info("Модуль базы данных готов к работе")
except Exception as e:
    error_msg = f"Не удалось инициализировать модуль базы данных: {str(e)}"
    error_logger.error(error_msg, exc_info=True)
    logger.critical(error_msg)
    raise