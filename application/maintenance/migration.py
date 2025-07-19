# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import os
import re
import hashlib
import time
from typing import Dict, List, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from maintenance.database_connector import get_db_session
from maintenance.logger import setup_logger

logger = setup_logger(__name__)
MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')

class MigrationError(Exception):
    """Класс для ошибок миграции с детальным логированием"""
    def __init__(self, message: str, migration_file: Optional[str] = None):
        self.message = message
        self.migration_file = migration_file
        logger.critical(
            f"ОШИБКА МИГРАЦИИ{' (' + migration_file + ')' if migration_file else ''}: {message}",
            exc_info=True
        )
        super().__init__(message)

def _log_migration_step(step: str, details: str = "", level: str = "info") -> None:
    """Унифицированное логирование шагов миграции"""
    log_method = getattr(logger, level.lower(), logger.info)
    border = "=" * 40
    log_method(f"\n{border}\nМИГРАЦИЯ: {step}\n{details}\n{border}")

def get_migration_files() -> List[str]:
    """
    Получаем список файлов миграций в правильном порядке с детальным логированием
    
    Возвращает:
        List[str]: Отсортированный список файлов миграций
        
    Вызывает:
        MigrationError: Если директория с миграциями не найдена или недоступна
    """
    try:
        _log_migration_step("Поиск файлов миграций", f"Директория: {MIGRATIONS_DIR}")
        
        if not os.path.exists(MIGRATIONS_DIR):
            error_msg = f"Директория с миграциями не найдена: {MIGRATIONS_DIR}"
            _log_migration_step("Ошибка", error_msg, "error")
            raise MigrationError(error_msg)

        files = []
        valid_files = []
        invalid_files = []
        
        for f in os.listdir(MIGRATIONS_DIR):
            full_path = os.path.join(MIGRATIONS_DIR, f)
            if os.path.isfile(full_path):
                files.append(f)
                if re.match(r'^\d{3}-.+\.sql$', f):
                    valid_files.append(f)
                else:
                    invalid_files.append(f)

        _log_migration_step(
            "Найдены файлы",
            f"Всего: {len(files)}\n"
            f"Валидных миграций: {len(valid_files)}\n"
            f"Невалидных файлов: {len(invalid_files)}\n"
            f"Пример невалидного: {invalid_files[0] if invalid_files else 'нет'}"
        )

        if not valid_files:
            error_msg = f"Не найдено ни одной валидной миграции в {MIGRATIONS_DIR}"
            _log_migration_step("Ошибка", error_msg, "error")
            raise MigrationError(error_msg)

        sorted_files = sorted(valid_files)
        _log_migration_step(
            "Сортировка миграций",
            f"Первая миграция: {sorted_files[0]}\n"
            f"Последняя миграция: {sorted_files[-1]}\n"
            f"Всего миграций: {len(sorted_files)}"
        )
        
        return sorted_files
        
    except Exception as e:
        error_msg = f"Ошибка чтения директории миграций: {str(e)}"
        _log_migration_step("Критическая ошибка", error_msg, "critical")
        raise MigrationError(error_msg) from e

def check_migrations_table(session) -> None:
    """
    Проверяем наличие таблицы миграций и создаем если ее нет
    
    Параметры:
        session: Сессия БД
        
    Вызывает:
        MigrationError: При ошибках создания таблицы
    """
    try:
        _log_migration_step("Проверка таблицы applied_migrations")
        
        # Проверка существования таблицы
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'applied_migrations'
            )
        """))
        exists = result.scalar()
        
        if exists:
            _log_migration_step("Таблица существует", "Продолжение без создания")
            return

        _log_migration_step("Создание таблицы applied_migrations")
        
        # Создание таблицы
        create_table_sql = """
            CREATE TABLE applied_migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                checksum VARCHAR(64) NOT NULL,
                execution_time_ms FLOAT
            )
        """
        session.execute(text(create_table_sql))
        session.commit()
        
        _log_migration_step("Таблица создана", "Успешно создана таблица applied_migrations")
        
    except SQLAlchemyError as e:
        session.rollback()
        error_msg = f"Ошибка создания таблицы миграций: {str(e)}"
        _log_migration_step("Ошибка SQL", error_msg, "error")
        raise MigrationError(error_msg) from e
    except Exception as e:
        session.rollback()
        error_msg = f"Неожиданная ошибка при работе с таблицей миграций: {str(e)}"
        _log_migration_step("Критическая ошибка", error_msg, "critical")
        raise MigrationError(error_msg) from e

def get_applied_migrations(session) -> Dict[str, Tuple[str, float]]:
    """
    Получаем список примененных миграций с дополнительной информацией
    
    Параметры:
        session: Сессия БД
        
    Возвращает:
        Dict[str, Tuple[str, float]]: {имя_файла: (контрольная_сумма, время_выполнения_мс)}
        
    Вызывает:
        MigrationError: При ошибках запроса к БД
    """
    try:
        _log_migration_step("Получение списка примененных миграций")
        
        result = session.execute(text("""
            SELECT name, checksum, execution_time_ms 
            FROM applied_migrations 
            ORDER BY applied_at
        """))
        
        migrations = {row[0]: (row[1], row[2]) for row in result.fetchall()}
        
        _log_migration_step(
            "Полученные миграции",
            f"Найдено примененных миграций: {len(migrations)}\n"
            f"Пример: {next(iter(migrations.items())) if migrations else 'нет'}"
        )
        
        return migrations
        
    except SQLAlchemyError as e:
        error_msg = f"Ошибка получения списка миграций: {str(e)}"
        _log_migration_step("Ошибка SQL", error_msg, "error")
        raise MigrationError(error_msg) from e
    except Exception as e:
        error_msg = f"Неожиданная ошибка при получении миграций: {str(e)}"
        _log_migration_step("Критическая ошибка", error_msg, "critical")
        raise MigrationError(error_msg) from e

def calculate_checksum(file_path: str) -> str:
    """
    Вычисляем SHA-256 контрольную сумму файла миграции
    
    Параметры:
        file_path: Путь к файлу миграции
        
    Возвращает:
        str: Контрольная сумма SHA-256
        
    Вызывает:
        MigrationError: При ошибках чтения файла
    """
    try:
        _log_migration_step("Вычисление контрольной суммы", f"Файл: {file_path}")
        
        with open(file_path, 'rb') as f:
            content = f.read()
            checksum = hashlib.sha256(content).hexdigest()
            
        _log_migration_step(
            "Контрольная сумма вычислена",
            f"Файл: {os.path.basename(file_path)}\n"
            f"Размер: {len(content)} байт\n"
            f"SHA-256: {checksum}"
        )
        
        return checksum
        
    except Exception as e:
        error_msg = f"Ошибка вычисления контрольной суммы для {file_path}: {str(e)}"
        _log_migration_step("Ошибка", error_msg, "error")
        raise MigrationError(error_msg, os.path.basename(file_path)) from e

def split_sql_statements(sql: str) -> List[str]:
    """
    Разбивает SQL-скрипт на отдельные запросы с учетом dollar-quoted блоков
    
    Параметры:
        sql: Исходный SQL-скрипт
        
    Возвращает:
        List[str]: Список отдельных SQL-запросов
    """
    _log_migration_step("Разбор SQL на отдельные запросы")
    
    statements = []
    current = ""
    in_dollar_quote = False
    dollar_quote_tag = ""
    line_num = 0
    statement_num = 0
    
    for line in sql.split('\n'):
        line_num += 1
        if not in_dollar_quote:
            dollar_match = re.search(r'\$([^\$]*)\$', line)
            if dollar_match:
                in_dollar_quote = True
                dollar_quote_tag = dollar_match.group(0)
                current += line + '\n'
                logger.debug(f"Начало dollar-quoted блока (строка {line_num}): {dollar_quote_tag}")
                continue
            
            if ';' in line:
                parts = line.split(';')
                for part in parts[:-1]:
                    current += part
                    if current.strip():
                        statement_num += 1
                        logger.debug(f"Запрос #{statement_num} (строка {line_num}):\n{current.strip()}")
                        statements.append(current.strip())
                    current = ""
                current += parts[-1] + '\n'
            else:
                current += line + '\n'
        else:
            current += line + '\n'
            if dollar_quote_tag in line:
                in_dollar_quote = False
                statement_num += 1
                logger.debug(f"Запрос #{statement_num} (dollar-quoted, строки {line_num-len(current.splitlines())+1}-{line_num}):\n{current.strip()}")
                statements.append(current.strip())
                current = ""
    
    if current.strip():
        statement_num += 1
        logger.debug(f"Запрос #{statement_num} (финальный):\n{current.strip()}")
        statements.append(current.strip())
    
    _log_migration_step(
        "Результат разбора SQL",
        f"Всего запросов: {len(statements)}\n"
        f"Пример запроса: {statements[0][:100] + '...' if statements else 'нет'}"
    )
    
    return [stmt for stmt in statements if stmt]

def apply_migration(session, migration_file: str) -> None:
    """
    Применяет одну миграцию с полным логированием каждого шага
    
    Параметры:
        session: Сессия БД
        migration_file: Имя файла миграции
        
    Вызывает:
        MigrationError: При ошибках выполнения миграции
    """
    start_time = time.time()
    file_path = os.path.join(MIGRATIONS_DIR, migration_file)
    
    try:
        _log_migration_step(
            "Начало применения миграции",
            f"Файл: {migration_file}\n"
            f"Полный путь: {file_path}"
        )
        
        # Вычисление контрольной суммы
        checksum = calculate_checksum(file_path)
        
        # Чтение SQL из файла
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
            logger.debug(f"Содержимое SQL (первые 500 символов):\n{sql[:500]}...")
        
        # Разбиение на отдельные запросы
        statements = split_sql_statements(sql)
        
        # Выполнение каждого запроса
        for i, query in enumerate(statements, 1):
            query_start = time.time()
            try:
                logger.debug(f"Выполнение запроса {i}/{len(statements)}...")
                session.execute(text(query))
                query_time = (time.time() - query_start) * 1000
                logger.debug(f"Запрос выполнен за {query_time:.2f} мс")
            except Exception as e:
                logger.error(f"Ошибка в запросе {i}:\n{query[:200]}...")
                raise
        
        # Фиксация миграции в БД
        execution_time = (time.time() - start_time) * 1000
        session.execute(
            text("""
                INSERT INTO applied_migrations 
                (name, checksum, execution_time_ms) 
                VALUES (:name, :checksum, :execution_time)
            """),
            {
                "name": migration_file, 
                "checksum": checksum,
                "execution_time": execution_time
            }
        )
        session.commit()
        
        _log_migration_step(
            "Миграция успешно применена",
            f"Файл: {migration_file}\n"
            f"Контрольная сумма: {checksum}\n"
            f"Время выполнения: {execution_time:.2f} мс\n"
            f"Количество запросов: {len(statements)}"
        )
        
    except Exception as e:
        session.rollback()
        error_msg = f"Ошибка применения миграции {migration_file}: {str(e)}"
        _log_migration_step("Ошибка", error_msg, "error")
        raise MigrationError(error_msg, migration_file) from e

def verify_applied_migrations(session) -> None:
    """
    Проверяет целостность примененных миграций
    
    Параметры:
        session: Сессия БД
        
    Вызывает:
        MigrationError: При обнаружении проблем
    """
    try:
        _log_migration_step("Проверка целостности миграций")
        
        applied = get_applied_migrations(session)
        files = get_migration_files()
        
        # Проверка отсутствующих миграций
        missing_in_files = set(applied.keys()) - set(files)
        if missing_in_files:
            error_msg = f"Примененные миграции отсутствуют в директории: {', '.join(missing_in_files)}"
            _log_migration_step("Ошибка", error_msg, "error")
            raise MigrationError(error_msg)
        
        # Проверка контрольных сумм
        for name, (checksum, _) in applied.items():
            current_checksum = calculate_checksum(os.path.join(MIGRATIONS_DIR, name))
            if current_checksum != checksum:
                error_msg = f"Контрольная сумма миграции {name} не совпадает (было: {checksum}, стало: {current_checksum})"
                _log_migration_step("Ошибка", error_msg, "error")
                raise MigrationError(error_msg, name)
        
        _log_migration_step(
            "Проверка целостности завершена",
            f"Проверено миграций: {len(applied)}\n"
            f"Все контрольные суммы совпадают"
        )
        
    except Exception as e:
        error_msg = f"Ошибка проверки миграций: {str(e)}"
        _log_migration_step("Критическая ошибка", error_msg, "critical")
        raise MigrationError(error_msg) from e

def run_migrations() -> List[str]:
    """
    Выполняет все непримененные миграции с детальным логированием
    
    Возвращает:
        List[str]: Список примененных миграций
        
    Вызывает:
        MigrationError: При ошибках выполнения миграций
    """
    total_start = time.time()
    applied_migrations = []
    
    try:
        _log_migration_step(
            "Запуск процесса миграций",
            f"Директория миграций: {MIGRATIONS_DIR}"
        )
        
        with get_db_session() as session:
            # Проверка и создание таблицы миграций
            check_migrations_table(session)
            
            # Проверка целостности существующих миграций
            verify_applied_migrations(session)
            
            # Получение списка примененных и доступных миграций
            applied = set(get_applied_migrations(session).keys())
            all_files = set(get_migration_files())
            pending = sorted(all_files - applied)
            
            _log_migration_step(
                "Статус миграций",
                f"Всего миграций доступно: {len(all_files)}\n"
                f"Уже применено: {len(applied)}\n"
                f"Ожидает применения: {len(pending)}\n"
                f"Список ожидающих: {', '.join(pending) if pending else 'нет'}"
            )
            
            if not pending:
                _log_migration_step(
                    "Нет новых миграций",
                    "Все миграции уже применены",
                    "info"
                )
                return []
            
            # Применение каждой миграции
            for migration_file in pending:
                try:
                    apply_migration(session, migration_file)
                    applied_migrations.append(migration_file)
                except Exception as e:
                    error_msg = f"Прерывание процесса миграций из-за ошибки в {migration_file}"
                    _log_migration_step("Критическая ошибка", error_msg, "critical")
                    raise
        
        total_time = (time.time() - total_start) * 1000
        _log_migration_step(
            "Все миграции успешно применены",
            f"Применено миграций: {len(applied_migrations)}\n"
            f"Общее время выполнения: {total_time:.2f} мс\n"
            f"Список примененных: {', '.join(applied_migrations)}"
        )
        
        return applied_migrations
        
    except Exception as e:
        error_msg = f"Ошибка выполнения миграций: {str(e)}"
        _log_migration_step("Критическая ошибка", error_msg, "critical")
        raise MigrationError(error_msg) from e

def check_migrations_status() -> Tuple[bool, List[str]]:
    """
    Проверяет состояние миграций с детальным логированием
    
    Возвращает:
        Tuple[bool, List[str]]: 
            - True если все миграции применены, False если есть непримененные
            - Список непримененных миграций
    """
    try:
        _log_migration_step("Проверка состояния миграций")
        
        with get_db_session() as session:
            check_migrations_table(session)
            verify_applied_migrations(session)
            
            applied = set(get_applied_migrations(session).keys())
            all_files = set(get_migration_files())
            pending = sorted(all_files - applied)
            
            status_msg = (
                f"Всего миграций: {len(all_files)}\n"
                f"Применено: {len(applied)}\n"
                f"Ожидает: {len(pending)}\n"
                f"Список ожидающих: {', '.join(pending) if pending else 'нет'}"
            )
            
            if pending:
                _log_migration_step(
                    "Обнаружены непримененные миграции", 
                    status_msg,
                    "warning"
                )
                return (False, pending)
            
            _log_migration_step(
                "Все миграции применены",
                status_msg,
                "info"
            )
            return (True, [])
            
    except Exception as e:
        error_msg = f"Ошибка проверки состояния миграций: {str(e)}"
        _log_migration_step("Ошибка", error_msg, "error")
        return (False, [])