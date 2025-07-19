# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import logging
import json
import os
import time
from typing import Optional
from pathlib import Path
from typing import Any, Dict, Optional, Union
from maintenance.logger import setup_logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = setup_logger(__name__)

class ConfigFileHandler(FileSystemEventHandler):
    """Обработчик событий изменения файла конфигурации"""
    
    def __init__(self, config_reader: 'ConfigReader'):
        self.config_reader = config_reader
        super().__init__()
    
    def on_modified(self, event):
        if Path(event.src_path) == self.config_reader._config_path:
            logger.info(f"Обнаружено изменение файла конфигурации: {event.src_path}")
            try:
                self.config_reader.reload()
                logger.info("Конфигурация успешно обновлена после изменения файла")
            except Exception as e:
                logger.error(
                    f"Не удалось обновить конфигурацию после изменения файла: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )

class ConfigReader:
    """
    Класс для чтения конфигурации с расширенным логированием всех операций.
    Реализует singleton-паттерн для единой точки доступа к конфигурации.
    Добавлен мониторинг изменений файла конфигурации.
    """

    _instance: Optional['ConfigReader'] = None
    _config: Optional[Dict[str, Any]] = None
    _config_path: Optional[Path] = None
    _initialized: bool = False
    _last_loaded: Optional[float] = None
    _observer: Optional[Observer] = None

    def __new__(cls):
        """Реализация singleton-паттерна с логированием"""
        if cls._instance is None:
            logger.debug("Инициализация нового экземпляра ConfigReader (singleton)")
            cls._instance = super(ConfigReader, cls).__new__(cls)
            if not cls._initialized:
                start_time = time.time()
                cls._init_config()
                cls._start_file_watcher()
                cls._initialized = True
                load_time = (time.time() - start_time) * 1000
                logger.info(f"ConfigReader инициализирован за {load_time:.2f} мс")
        else:
            logger.debug("Использование существующего экземпляра ConfigReader")
        return cls._instance

    @classmethod
    def _start_file_watcher(cls):
        """Запуск мониторинга изменений файла конфигурации"""
        if cls._config_path is None:
            return
            
        try:
            logger.info(f"Запуск мониторинга файла конфигурации: {cls._config_path}")
            event_handler = ConfigFileHandler(cls._instance)
            cls._observer = Observer()
            cls._observer.schedule(
                event_handler, 
                path=str(cls._config_path.parent), 
                recursive=False
            )
            cls._observer.start()
            logger.debug("Мониторинг файла конфигурации успешно запущен")
        except Exception as e:
            logger.error(
                f"Не удалось запустить мониторинг файла конфигурации: {type(e).__name__}: {str(e)}",
                exc_info=True
            )

    @classmethod
    def _stop_file_watcher(cls):
        """Остановка мониторинга изменений файла конфигурации"""
        if cls._observer is not None:
            try:
                logger.info("Остановка мониторинга файла конфигурации")
                cls._observer.stop()
                cls._observer.join()
                logger.debug("Мониторинг файла конфигурации успешно остановлен")
            except Exception as e:
                logger.error(
                    f"Не удалось остановить мониторинг файла конфигурации: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )

    @classmethod
    def _init_config(cls):
        """Инициализация и загрузка конфигурации с детальным логированием"""
        try:
            logger.info("Начало инициализации конфигурации")
            
            # Определение пути к конфигурационному файлу
            base_dir = Path(__file__).parent.parent
            cls._config_path = base_dir / 'configurations' / 'config.json'
            
            logger.debug(f"Поиск конфигурационного файла по пути: {cls._config_path.absolute()}")
            logger.debug(f"Родительский каталог существует: {(cls._config_path.parent.exists())}")
            logger.debug(f"Содержимое каталога: {list(cls._config_path.parent.glob('*'))}")

            if not cls._config_path.exists():
                error_msg = f"Файл конфигурации не найден: {cls._config_path}"
                logger.critical(error_msg)
                raise FileNotFoundError(error_msg)

            logger.info(f"Конфигурационный файл найден: {cls._config_path}")
            logger.debug(f"Размер файла: {cls._config_path.stat().st_size} байт")
            logger.debug(f"Время последнего изменения: {cls._config_path.stat().st_mtime}")

            cls._load_config()
            
        except Exception as e:
            logger.critical(
                f"КРИТИЧЕСКАЯ ОШИБКА ИНИЦИАЛИЗАЦИИ КОНФИГУРАЦИИ: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise RuntimeError("Не удалось инициализировать конфигурацию") from e

    @classmethod
    def _load_config(cls):
        """Загрузка и валидация конфигурационного файла"""
        try:
            start_time = time.time()
            logger.debug(f"Начало загрузки конфигурации из {cls._config_path}")

            with open(cls._config_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
                logger.debug(f"Сырое содержимое файла (первые 500 символов):\n{raw_content[:500]}...")
                
                cls._config = json.loads(raw_content)
                cls._last_loaded = time.time()

            load_time = (time.time() - start_time) * 1000
            logger.info(f"Конфигурация успешно загружена за {load_time:.2f} мс")
            logger.debug(f"Тип загруженной конфигурации: {type(cls._config).__name__}")
            logger.debug(f"Количество корневых ключей: {len(cls._config)}")

            # Детальное логирование структуры конфигурации
            if logger.isEnabledFor(logging.DEBUG):
                config_summary = {
                    'keys': list(cls._config.keys()),
                    'types': {k: type(v).__name__ for k, v in cls._config.items()}
                }
                logger.debug(f"Структура конфигурации:\n{json.dumps(config_summary, indent=2)}")

            # Базовая валидация конфигурации
            if not isinstance(cls._config, dict):
                error_msg = f"Некорректный формат конфигурации (ожидался dict, получен {type(cls._config).__name__})"
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.debug("Базовая валидация конфигурации пройдена успешно")
            
        except json.JSONDecodeError as e:
            logger.error(
                f"ОШИБКА ПАРСИНГА JSON: {str(e)}\n"
                f"Строка: {e.lineno}, Колонка: {e.colno}\n"
                f"Контекст: {e.doc[e.pos-50:e.pos+50]}"
            )
            raise
        except Exception as e:
            logger.error(
                f"НЕОЖИДАННАЯ ОШИБКА ПРИ ЗАГРУЗКЕ КОНФИГУРАЦИИ: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise

    def __del__(self):
        """Остановка мониторинга при уничтожении экземпляра"""
        self._stop_file_watcher()

    def get(self, path: str, default: Any = None) -> Any:
        """
        Безопасное получение значения из конфигурации по пути вида 'section.key.subkey'
        
        Параметры:
            path (str): Путь к значению через точки
            default (Any): Значение по умолчанию, если путь не найден
            
        Возвращает:
            Any: Найденное значение или default
            
        Вызывает:
            KeyError: Если путь не существует и не указано default
        """
        try:
            start_time = time.time()
            logger.debug(f"Запрос значения конфигурации: '{path}'")

            if self._config is None:
                logger.warning("Конфигурация не загружена, выполняется повторная загрузка")
                self._load_config()

            keys = path.split('.')
            current = self._config
            full_path = []

            for key in keys:
                full_path.append(key)
                current_path = '.'.join(full_path)
                
                if not isinstance(current, dict):
                    error_msg = f"Попытка обращения к '{key}' в не-словаре (полный путь: '{current_path}')"
                    logger.error(error_msg)
                    raise KeyError(error_msg)
                
                if key not in current:
                    error_msg = f"Ключ не найден: '{current_path}'"
                    if default is not None:
                        logger.warning(f"{error_msg}, будет использовано значение по умолчанию: {default}")
                        return default
                    logger.error(error_msg)
                    raise KeyError(error_msg)
                
                current = current[key]
                logger.debug(f"Переход по пути: '{current_path}' -> тип: {type(current).__name__}")

            logger.info(
                f"Значение найдено: '{path}' = {current} "
                f"(тип: {type(current).__name__}, время поиска: {(time.time()-start_time)*1000:.2f} мс)"
            )
            return current
            
        except Exception as e:
            logger.error(
                f"ОШИБКА ПОЛУЧЕНИЯ ЗНАЧЕНИЯ '{path}': {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise

    def __getattr__(self, name: str) -> Any:
        """
        Доступ к разделам конфигурации через атрибуты (config.section)
        
        Параметры:
            name (str): Имя раздела конфигурации
            
        Возвращает:
            Any: Значение раздела конфигурации
            
        Вызывает:
            AttributeError: Если раздел не существует
        """
        try:
            logger.debug(f"Запрос раздела конфигурации через атрибут: '{name}'")

            if self._config is None:
                logger.warning("Конфигурация не загружена, выполняется повторная загрузка")
                self._load_config()

            if name not in self._config:
                error_msg = f"Раздел конфигурации не найден: '{name}'"
                logger.error(error_msg)
                raise AttributeError(error_msg)

            value = self._config[name]
            logger.info(
                f"Раздел конфигурации получен: '{name}' -> тип: {type(value).__name__}, "
                f"размер: {len(value) if isinstance(value, (dict, list)) else 'N/A'}"
            )
            return value
            
        except Exception as e:
            logger.error(
                f"ОШИБКА ПОЛУЧЕНИЯ РАЗДЕЛА '{name}': {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise

    def reload(self) -> None:
        """Принудительная перезагрузка конфигурации с логированием"""
        try:
            logger.warning("Инициирована принудительная перезагрузка конфигурации")
            self._load_config()
            logger.info("Конфигурация успешно перезагружена")
        except Exception as e:
            logger.critical(
                f"НЕУДАЧНАЯ ПЕРЕЗАГРУЗКА КОНФИГУРАЦИИ: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise

# Инициализация глобального экземпляра конфигурации
try:
    logger.info("=" * 80)
    logger.info("НАЧАЛО ИНИЦИАЛИЗАЦИИ ГЛОБАЛЬНОЙ КОНФИГУРАЦИИ")
    start_time = time.time()
    
    config = ConfigReader()
    
    init_time = (time.time() - start_time) * 1000
    logger.info(
        f"ГЛОБАЛЬНАЯ КОНФИГУРАЦИЯ УСПЕШНО ИНИЦИАЛИЗИРОВАНА "
        f"(за {init_time:.2f} мс, {len(config._config or {})} ключей)"
    )
    logger.info("=" * 80)
    
except Exception as e:
    logger.critical(
        "=" * 80 + "\n" +
        "КРИТИЧЕСКАЯ ОШИБКА ИНИЦИАЛИЗАЦИИ КОНФИГУРАЦИИ:\n" +
        f"Тип: {type(e).__name__}\n" +
        f"Сообщение: {str(e)}\n" +
        "=" * 80,
        exc_info=True
    )
    raise RuntimeError("Не удалось загрузить конфигурацию приложения") from e