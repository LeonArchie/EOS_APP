# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import json
import logging
import time
from typing import Optional, Iterator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import (
    OperationalError,
    DatabaseError,
    DataError,
    IntegrityError,
    ProgrammingError,
    InternalError,
    InterfaceError,
    TimeoutError,
    SQLAlchemyError
)
from contextlib import contextmanager
from maintenance.read_config import config
from maintenance.logger import setup_logger

logger = setup_logger(__name__)
error_logger = logging.getLogger(f"{__name__}.errors")
error_logger.setLevel(logging.ERROR)

# Конфигурация подключения к БД
DB_CONFIG = {
    'host': config.get('db.master_host'),
    'port': config.get('db.master_port'),
    'database': config.get('db.database'),
    'user': config.get('db.user'),
    'password': '***' if config.get('db.password') else 'None',  # Скрываем пароль в логах
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
engine = None  # type: Optional[create_engine]
SessionLocal = None  # type: Optional[scoped_session]
Base = declarative_base()
_initialized = False

def _log_db_operation(operation: str, details: str = "", level: str = "info") -> None:
    """Унифицированное логирование операций с БД"""
    log_method = getattr(logger, level.lower(), logger.info)
    border = "=" * 60
    log_method(f"\n{border}\nOPERATION: {operation}\n{details}\n{border}")

class DatabaseErrorHandler:
    """Класс для обработки ошибок базы данных с детальным логированием."""
    
    ERROR_MAPPING = {
        OperationalError: {
            'code': 'db_connection_error',
            'message': "Ошибка подключения к базе данных",
            'log_level': logging.ERROR,
            'retryable': True
        },
        DataError: {
            'code': 'db_data_error',
            'message': "Ошибка данных в запросе",
            'log_level': logging.WARNING,
            'retryable': False
        },
        IntegrityError: {
            'code': 'db_integrity_error',
            'message': "Нарушение целостности данных",
            'log_level': logging.WARNING,
            'retryable': False
        },
        ProgrammingError: {
            'code': 'db_programming_error',
            'message': "Ошибка в SQL запросе",
            'log_level': logging.ERROR,
            'retryable': False
        },
        InternalError: {
            'code': 'db_internal_error',
            'message': "Внутренняя ошибка базы данных",
            'log_level': logging.CRITICAL,
            'retryable': True
        },
        InterfaceError: {
            'code': 'db_interface_error',
            'message': "Ошибка интерфейса базы данных",
            'log_level': logging.CRITICAL,
            'retryable': True
        },
        TimeoutError: {
            'code': 'db_timeout_error',
            'message': "Таймаут операции с базой данных",
            'log_level': logging.WARNING,
            'retryable': True
        },
        DatabaseError: {
            'code': 'db_generic_error',
            'message': "Ошибка базы данных",
            'log_level': logging.ERROR,
            'retryable': False
        }
    }
    
    @classmethod
    def handle_error(cls, error: SQLAlchemyError, context: Optional[Dict[str, Any]] = None) -> None:
        """Обработка ошибки базы данных с детальным логированием контекста."""
        error_type = type(error)
        error_info = cls.ERROR_MAPPING.get(error_type, {
            'code': 'db_unknown_error',
            'message': "Неизвестная ошибка базы данных",
            'log_level': logging.CRITICAL,
            'retryable': False
        })
        
        # Формирование детального сообщения об ошибке
        error_details = [
            f"Тип: {error_type.__name__}",
            f"Код: {error_info['code']}",
            f"Сообщение: {str(error)}",
            f"Можно повторить: {'Да' if error_info['retryable'] else 'Нет'}"
        ]
        
        if context:
            error_details.append("Контекст ошибки:")
            for key, value in context.items():
                error_details.append(f"  {key}: {value}")
        
        error_logger.log(
            error_info['log_level'],
            "\n".join(error_details),
            exc_info=True
        )
        
        raise RuntimeError(f"{error_info['message']} (код: {error_info['code']})") from error

def get_db_connection_string() -> str:
    """Генерация строки подключения к БД с логированием."""
    _log_db_operation(
        "Генерация строки подключения",
        f"Хост: {DB_CONFIG['host']}\n"
        f"Порт: {DB_CONFIG['port']}\n"
        f"База данных: {DB_CONFIG['database']}\n"
        f"Пользователь: {DB_CONFIG['user']}"
    )
    
    return (
        f"postgresql://{DB_CONFIG['user']}:{config.get('db.password')}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

def get_db_engine() -> create_engine:
    """Получение инициализированного engine БД с проверкой состояния."""
    if not _initialized:
        error_msg = "Попытка получить engine неинициализированной БД"
        error_logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    _log_db_operation(
        "Получение engine БД",
        f"Состояние пула: {engine.pool.status()}\n"
        f"Количество соединений: {engine.pool.checkedin() + engine.pool.checkedout()}"
    )
    return engine

def initialize_database() -> None:
    """Инициализация подключения к базе данных с детальным логированием."""
    global engine, SessionLocal, _initialized
    
    if _initialized:
        _log_db_operation(
            "Повторная инициализация БД",
            "Попытка повторной инициализации уже работающего подключения",
            "warning"
        )
        return
    
    start_time = time.time()
    try:
        _log_db_operation(
            "Начало инициализации БД",
            f"Конфигурация:\n{json.dumps(DB_CONFIG, indent=2)}"
        )
        
        connection_string = get_db_connection_string()
        logger.debug(f"Полная строка подключения: {connection_string}")
        
        _log_db_operation("Создание engine БД")
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
        _log_db_operation("Проверка подключения к БД")
        try:
            test_start = time.time()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1, version()"))
                row = result.fetchone()
                test_time = (time.time() - test_start) * 1000
                
                _log_db_operation(
                    "Проверка подключения успешна",
                    f"Время выполнения: {test_time:.2f} мс\n"
                    f"Результат: {row[0]}\n"
                    f"Версия СУБД: {row[1]}"
                )
        except SQLAlchemyError as e:
            DatabaseErrorHandler.handle_error(e, {
                'operation': 'connection_test',
                'connection_string': connection_string
            })
        
        # Инициализация сессий
        _log_db_operation("Инициализация сессий БД")
        SessionLocal = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine,
                expire_on_commit=False
            )
        )
        
        _initialized = True
        init_time = (time.time() - start_time) * 1000
        _log_db_operation(
            "Инициализация БД завершена",
            f"Общее время: {init_time:.2f} мс\n"
            f"Размер пула: {DB_CONFIG['pool_size']}\n"
            f"Макс. переполнение: {DB_CONFIG['max_overflow']}"
        )
        
    except Exception as e:
        init_time = (time.time() - start_time) * 1000
        _log_db_operation(
            "Ошибка инициализации БД",
            f"Время до ошибки: {init_time:.2f} мс\n"
            f"Тип ошибки: {type(e).__name__}",
            "critical"
        )
        if engine:
            engine.dispose()
        raise

@contextmanager
def get_db_session() -> Iterator[scoped_session]:
    """Контекстный менеджер для работы с сессией БД с полным логированием."""
    session_start = time.time()
    
    if not _initialized:
        error_msg = "Попытка создать сессию неинициализированной БД"
        error_logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    session = SessionLocal()
    session_id = id(session)
    
    try:
        _log_db_operation(
            "Открытие сессии БД",
            f"ID сессии: {session_id}\n"
            f"Время начала: {time.ctime(session_start)}"
        )
        
        yield session
        
        commit_start = time.time()
        session.commit()
        commit_time = (time.time() - commit_start) * 1000
        
        _log_db_operation(
            "Успешное завершение сессии",
            f"ID сессии: {session_id}\n"
            f"Время коммита: {commit_time:.2f} мс\n"
            f"Общее время: {(time.time() - session_start) * 1000:.2f} мс"
        )
        
    except SQLAlchemyError as e:
        rollback_start = time.time()
        session.rollback()
        rollback_time = (time.time() - rollback_start) * 1000
        
        DatabaseErrorHandler.handle_error(e, {
            'session_id': session_id,
            'operation_time': f"{(time.time() - session_start) * 1000:.2f} мс",
            'rollback_time': f"{rollback_time:.2f} мс"
        })
        
    except Exception as e:
        rollback_start = time.time()
        session.rollback()
        rollback_time = (time.time() - rollback_start) * 1000
        
        error_logger.error(
            f"Неожиданная ошибка в сессии {session_id}:\n"
            f"Тип: {type(e).__name__}\n"
            f"Сообщение: {str(e)}\n"
            f"Время работы: {(time.time() - session_start) * 1000:.2f} мс\n"
            f"Время отката: {rollback_time:.2f} мс",
            exc_info=True
        )
        raise RuntimeError("Неожиданная ошибка при работе с БД") from e
        
    finally:
        close_start = time.time()
        session.close()
        if SessionLocal.registry.has():
            SessionLocal.remove()
        
        _log_db_operation(
            "Закрытие сессии БД",
            f"ID сессии: {session_id}\n"
            f"Время закрытия: {(time.time() - close_start) * 1000:.2f} мс"
        )

def close_connection_pool() -> None:
    """Закрытие пула подключений к БД с детальным логированием."""
    global engine, _initialized
    
    if not engine:
        _log_db_operation(
            "Закрытие пула подключений",
            "Попытка закрыть несуществующий engine",
            "warning"
        )
        return
    
    _log_db_operation(
        "Начало закрытия пула подключений",
        f"Текущий размер пула: {engine.pool.size()}\n"
        f"Активные соединения: {engine.pool.checkedout()}"
    )
    
    start_time = time.time()
    try:
        engine.dispose()
        _initialized = False
        
        _log_db_operation(
            "Пул подключений закрыт",
            f"Время выполнения: {(time.time() - start_time) * 1000:.2f} мс"
        )
    except Exception as e:
        _log_db_operation(
            "Ошибка закрытия пула",
            f"Тип: {type(e).__name__}\n"
            f"Сообщение: {str(e)}",
            "error"
        )
        raise

def is_database_initialized() -> bool:
    """Проверка инициализации подключения к БД с логированием."""
    status = _initialized
    logger.debug(f"Проверка состояния инициализации БД: {'Инициализирована' if status else 'Не инициализирована'}")
    return status