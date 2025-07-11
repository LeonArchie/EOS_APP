# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import json
import os
from pathlib import Path
from typing import Any, Dict
from maintenance.logger import setup_logger

logger = setup_logger(__name__)

class ConfigReader:
    """
    Класс для безопасного чтения конфигурации с детальным логированием
    """
    _instance = None
    _config = None
    _config_path = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            logger.debug("Создание нового экземпляра ConfigReader")
            cls._instance = super(ConfigReader, cls).__new__(cls)
            if not cls._initialized:
                cls._init_config()
                cls._initialized = True
        return cls._instance

    @classmethod
    def _init_config(cls):
        """Инициализация пути к конфигурационному файлу"""
        try:
            base_dir = Path(__file__).parent.parent
            cls._config_path = base_dir / 'configurations' / 'config.json'
            logger.info(f"Инициализация конфигурации. Ожидаемый путь: {cls._config_path}")
            
            if not cls._config_path.exists():
                logger.error(f"Файл конфигурации не найден по пути: {cls._config_path}")
                raise FileNotFoundError(f"Файл конфигурации не найден: {cls._config_path}")
            
            cls._load_config()
            
        except Exception as e:
            logger.critical(f"Критическая ошибка при инициализации конфигурации: {str(e)}")
            raise

    @classmethod
    def _load_config(cls):
        """Загрузка и валидация конфигурации"""
        try:
            with open(cls._config_path, 'r', encoding='utf-8') as f:
                cls._config = json.load(f)
            logger.info("Конфигурация успешно загружена из файла")
            logger.debug(f"Содержимое конфигурации: {json.dumps(cls._config, indent=2, ensure_ascii=False)}")
            
            # Базовая валидация
            if not isinstance(cls._config, dict):
                logger.error("Конфигурация должна быть словарем")
                raise ValueError("Некорректный формат конфигурации")
                
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке конфигурации: {str(e)}")
            raise

    def get(self, path: str, default: Any = None) -> Any:
        """
        Безопасное получение значения по пути (например 'app.port')
        """
        logger.debug(f"Запрос значения конфигурации по пути: '{path}'")
        
        if self._config is None:
            logger.warning("Конфигурация не загружена, выполняется повторная загрузка")
            self._load_config()
        
        keys = path.split('.')
        value = self._config
        
        try:
            for key in keys:
                if not isinstance(value, dict):
                    raise KeyError(f"Попытка обращения к ключу '{key}' не в словаре")
                value = value[key]
                
            logger.debug(f"Значение найдено: {path} = {value}")
            return value
            
        except KeyError:
            if default is not None:
                logger.warning(f"Используется значение по умолчанию для '{path}': {default}")
                return default
            logger.error(f"Не найдено значение конфигурации: '{path}'")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении значения '{path}': {str(e)}")
            raise

    def __getattr__(self, name: str) -> Any:
        """Доступ к разделам конфигурации через точку"""
        logger.debug(f"Запрос раздела конфигурации: '{name}'")
        
        if self._config is None:
            logger.warning("Конфигурация не загружена, выполняется повторная загрузка")
            self._load_config()
        
        if name not in self._config:
            logger.error(f"Раздел конфигурации не найден: '{name}'")
            raise AttributeError(f"Раздел '{name}' не существует в конфигурации")
            
        value = self._config[name]
        logger.debug(f"Значение раздела '{name}': {value}")
        return value

# Инициализация конфигурации при импорте
try:
    logger.info("Начало инициализации модуля конфигурации")
    config = ConfigReader()
    logger.info("Модуль конфигурации успешно инициализирован")
except Exception as e:
    logger.critical(f"ОШИБКА ИНИЦИАЛИЗАЦИИ КОНФИГУРАЦИИ: {str(e)}")
    raise