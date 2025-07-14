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

logger = setup_logger(__name__)
error_logger = logging.getLogger(f"{__name__}.errors")
error_logger.setLevel(logging.ERROR)

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

engine = None
SessionLocal = None
Base = None
_initialized = False

def get_db_engine():
    """Возвращает инициализированный engine БД"""
    global engine
    if not _initialized:
        raise RuntimeError("База данных не инициализирована")
    return engine

def initialize_database():
    global engine, SessionLocal, Base, _initialized
    
    if _initialized:
        logger.warning("Попытка повторной инициализации базы данных")
        return
    
    try:
        logger.info("Инициализация подключения к базе данных")
        
        connection_string = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )
        
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
        
        # Проверка подключения с явной транзакцией
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SELECT 1"))
        
        SessionLocal = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
                expire_on_commit=False
            )
        )
        
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
    if not _initialized:
        raise RuntimeError("База данных не инициализирована. Вызовите initialize_database()")
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        error_logger.error(f"Ошибка в транзакции БД: {str(e)}", exc_info=True)
        raise
    finally:
        session.close()
        if SessionLocal.registry.has():
            SessionLocal.remove()

def close_connection_pool():
    global engine, _initialized
    if engine:
        engine.dispose()
        _initialized = False
        logger.info("Пул подключений закрыт")