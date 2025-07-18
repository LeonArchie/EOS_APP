# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import os
import re
import hashlib
from typing import Dict, List
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
from maintenance.database_connector import get_db_session
from maintenance.logger import setup_logger

logger = setup_logger(__name__)
MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')

class MigrationError(Exception):
    """Класс для ошибок миграции"""
    pass

def get_migration_files() -> List[str]:
    """
    Получаем список файлов миграций в правильном порядке
    :return: Отсортированный список файлов миграций
    :raises MigrationError: Если директория с миграциями не найдена или недоступна
    """
    if not os.path.exists(MIGRATIONS_DIR):
        logger.error(f"Директория с миграциями не найдена: {MIGRATIONS_DIR}")
        raise MigrationError("Директория с миграциями не найдена")

    try:
        files = [f for f in os.listdir(MIGRATIONS_DIR) 
                if re.match(r'^\d{3}-.+\.sql$', f) and os.path.isfile(os.path.join(MIGRATIONS_DIR, f))]
        return sorted(files)
    except Exception as e:
        logger.error(f"Ошибка чтения директории миграций: {str(e)}")
        raise MigrationError("Ошибка чтения директории миграций")

def check_migrations_table(session) -> None:
    """
    Проверяем наличие таблицы миграций и создаем если ее нет
    :param session: Сессия БД
    :raises MigrationError: При ошибках создания таблицы
    """
    try:
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'applied_migrations'
            )
        """))
        if not result.scalar():
            logger.info("Создание таблицы applied_migrations")
            session.execute(text("""
                CREATE TABLE applied_migrations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    checksum VARCHAR(64) NOT NULL
                )
            """))
            session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Ошибка создания таблицы миграций: {str(e)}")
        raise MigrationError("Ошибка создания таблицы миграций")

def get_applied_migrations(session) -> Dict[str, str]:
    """
    Получаем список примененных миграций
    :param session: Сессия БД
    :return: Словарь {имя_файла: контрольная_сумма}
    :raises MigrationError: При ошибках запроса к БД
    """
    try:
        result = session.execute(text("SELECT name, checksum FROM applied_migrations ORDER BY id"))
        return {row[0]: row[1] for row in result.fetchall()}
    except SQLAlchemyError as e:
        logger.error(f"Ошибка получения списка миграций: {str(e)}")
        raise MigrationError("Ошибка получения списка миграций")

def calculate_checksum(file_path: str) -> str:
    """
    Вычисляем SHA-256 контрольную сумму файла миграции
    :param file_path: Путь к файлу миграции
    :return: Контрольная сумма SHA-256
    :raises MigrationError: При ошибках чтения файла
    """
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Ошибка вычисления контрольной суммы: {str(e)}")
        raise MigrationError("Ошибка вычисления контрольной суммы")

def split_sql_statements(sql: str) -> List[str]:
    """
    Разбивает SQL-скрипт на отдельные запросы с учетом dollar-quoted блоков
    :param sql: Исходный SQL-скрипт
    :return: Список отдельных SQL-запросов
    """
    statements = []
    current = ""
    in_dollar_quote = False
    dollar_quote_tag = ""
    
    for line in sql.split('\n'):
        if not in_dollar_quote:
            # Проверяем начало dollar-quoted блока
            dollar_match = re.search(r'\$([^\$]*)\$', line)
            if dollar_match:
                in_dollar_quote = True
                dollar_quote_tag = dollar_match.group(0)
                current += line + '\n'
                continue
            
            # Разбиваем по точкам с запятой вне dollar-quoted блоков
            if ';' in line:
                parts = line.split(';')
                for part in parts[:-1]:
                    current += part
                    if current.strip():  # Не добавляем пустые запросы
                        statements.append(current.strip())
                    current = ""
                current += parts[-1] + '\n'
            else:
                current += line + '\n'
        else:
            current += line + '\n'
            # Проверяем конец dollar-quoted блока
            if dollar_quote_tag in line:
                in_dollar_quote = False
                statements.append(current.strip())
                current = ""
    
    if current.strip():
        statements.append(current.strip())
    
    return [stmt for stmt in statements if stmt]

def apply_migration(session, migration_file: str) -> None:
    """
    Применяет одну миграцию
    :param session: Сессия БД
    :param migration_file: Имя файла миграции
    :raises MigrationError: При ошибках выполнения миграции
    """
    file_path = os.path.join(MIGRATIONS_DIR, migration_file)
    checksum = calculate_checksum(file_path)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        statements = split_sql_statements(sql)

        for query in statements:
            session.execute(text(query))
        
        session.execute(
            text("INSERT INTO applied_migrations (name, checksum) VALUES (:name, :checksum)"),
            {"name": migration_file, "checksum": checksum}
        )
        session.commit()
        logger.info(f"Применена миграция: {migration_file}")
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка применения миграции {migration_file}: {str(e)}", exc_info=True)
        raise MigrationError("Ошибка применения миграции")

def verify_applied_migrations(session) -> None:
    """
    Проверяет целостность примененных миграций
    :param session: Сессия БД
    :raises MigrationError: При обнаружении проблем
    """
    try:
        applied = get_applied_migrations(session)
        files = get_migration_files()

        # Проверяем, что все примененные миграции существуют
        for name, checksum in applied.items():
            if name not in files:
                logger.error(f"Примененная миграция {name} отсутствует в директории")
                raise MigrationError("Отсутствует примененная миграция")
            
            current_checksum = calculate_checksum(os.path.join(MIGRATIONS_DIR, name))
            if current_checksum != checksum:
                logger.error(f"Контрольная сумма миграции {name} не совпадает")
                raise MigrationError("Несовпадение контрольной суммы")
    except Exception as e:
        logger.error(f"Ошибка проверки миграций: {str(e)}")
        raise MigrationError("Ошибка проверки миграций")

def run_migrations() -> None:
    """
    Выполняет все непримененные миграции
    :raises MigrationError: При ошибках выполнения миграций
    """
    logger.info("Запуск миграций базы данных...")
    
    try:
        with get_db_session() as session:
            check_migrations_table(session)
            verify_applied_migrations(session)

            applied = get_applied_migrations(session)
            for migration_file in get_migration_files():
                if migration_file not in applied:
                    logger.info(f"Применение миграции: {migration_file}")
                    apply_migration(session, migration_file)

            logger.info("Все миграции успешно применены")
    except Exception as e:
        logger.critical(f"Ошибка выполнения миграций: {str(e)}", exc_info=True)
        raise MigrationError("Ошибка выполнения миграций")

def check_migrations_status() -> bool:
    """
    Проверяет состояние миграций
    :return: True если все миграции применены, False если есть непримененные
    """
    try:
        with get_db_session() as session:
            check_migrations_table(session)
            verify_applied_migrations(session)
            
            pending = set(get_migration_files()) - set(get_applied_migrations(session).keys())
            if pending:
                logger.warning(f"Ожидают применения миграции: {', '.join(pending)}")
                return False
            return True
    except Exception as e:
        logger.error(f"Ошибка проверки состояния миграций: {str(e)}")
        return False