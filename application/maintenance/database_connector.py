# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import logging
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError
from contextlib import contextmanager
from maintenance.read_config import config
from maintenance.logger import setup_logger

# Инициализация логгеров
logger = setup_logger(__name__)
error_logger = logging.getLogger(f"{__name__}.errors")
error_logger.setLevel(logging.ERROR)

# Конфигурация подключения к БД
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
    'pool_pre_ping': config.get('db.pool_pre_ping', True),
    'pool_use_lifo': config.get('db.pool_use_lifo', False),
    'replication': config.get('db.replication', 'false'),
    'replica_host': config.get('db.replica_host', ''),
    'replica_port': config.get('db.replica_port', 5432)
}

# Глобальные переменные для хранения состояния подключения
engine = None
SessionLocal = None
Base = None
_initialized = False

def get_db_connection_string():
    """
    Генерация строки подключения к БД на основе конфигурации
    :return: Строка подключения в формате PostgreSQL
    """
    logger.debug("Генерация строки подключения к БД")
    return (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

def get_db_engine():
    """
    Получение инициализированного engine БД
    :return: Объект engine SQLAlchemy
    :raises RuntimeError: Если БД не инициализирована
    """
    global engine
    if not _initialized:
        error_msg = "База данных не инициализирована"
        error_logger.error(error_msg)
        raise RuntimeError(error_msg)
    return engine

def initialize_database():
    """
    Инициализация подключения к базе данных:
    - создание engine с пулом подключений
    - настройка фабрики сессий
    - проверка подключения
    :raises RuntimeError: При ошибках подключения
    """
    global engine, SessionLocal, Base, _initialized
    
    if _initialized:
        logger.warning("Попытка повторной инициализации БД")
        return
    
    try:
        logger.info("Начало инициализации подключения к БД")
        
        # Генерация строки подключения
        connection_string = get_db_connection_string()
        logger.debug(f"Используемая строка подключения: {connection_string}")
        
        # Создание engine с настройками пула подключений
        engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=DB_CONFIG['pool_size'],
            max_overflow=DB_CONFIG['max_overflow'],
            pool_timeout=DB_CONFIG['pool_timeout'],
            pool_recycle=DB_CONFIG['pool_recycle'],
            pool_pre_ping=DB_CONFIG['pool_pre_ping'],
            pool_use_lifo=DB_CONFIG['pool_use_lifo'],
            echo=False,
            connect_args={
                'connect_timeout': 5,
                'application_name': 'EOS_App'
            }
        )
        
        # Проверка подключения
        logger.debug("Проверка подключения к БД")
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SELECT 1"))
        
        # Настройка фабрики сессий
        SessionLocal = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
                expire_on_commit=False
            )
        )
        
        # Инициализация базового класса для моделей
        Base = declarative_base()
        _initialized = True
        logger.info("Пул подключений успешно инициализирован")
        
    except OperationalError as e:
        error_msg = f"Ошибка подключения к БД: {str(e)}"
        error_logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Критическая ошибка инициализации БД: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg)

@contextmanager
def get_db_session():
    """
    Контекстный менеджер для работы с сессией БД
    :yield: Сессия БД
    :raises RuntimeError: Если БД не инициализирована
    """
    if not _initialized:
        error_msg = "База данных не инициализирована. Вызовите initialize_database()"
        error_logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    session = SessionLocal()
    try:
        logger.debug("Открытие новой сессии БД")
        yield session
        session.commit()
        logger.debug("Сессия БД успешно завершена, изменения зафиксированы")
    except Exception as e:
        session.rollback()
        error_msg = f"Ошибка в транзакции БД: {str(e)}"
        error_logger.error(error_msg, exc_info=True)
        raise
    finally:
        session.close()
        logger.debug("Сессия БД закрыта")
        if SessionLocal.registry.has():
            SessionLocal.remove()

def close_connection_pool():
    """
    Закрытие пула подключений к БД
    """
    global engine, _initialized
    if engine:
        logger.info("Закрытие пула подключений к БД")
        engine.dispose()
        _initialized = False
        logger.info("Пул подключений успешно закрыт")
    else:
        logger.warning("Попытка закрыть неинициализированный пул подключений")