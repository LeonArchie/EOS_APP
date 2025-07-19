# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from datetime import datetime, timedelta, timezone
import jwt
import hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes, PublicKeyTypes
from typing import Dict, Union, Optional, Tuple
from maintenance.database_connector import get_db_session
from maintenance.read_config import config
from maintenance.logger import setup_logger
from sqlalchemy import text
import json
import time

logger = setup_logger(__name__)

class JWTService:
    """Сервис для работы с JWT-токенами и сессиями с расширенным логированием."""
    
    _secret = config.get('app.jwt_key')
    _access_expires = config.get('app.access_expires', 600)      # 10 минут
    _refresh_expires = config.get('app.refresh_expires', 1200)   # 20 минут
    _max_sessions = config.get('app.count_session', 5)
    
    # RSA ключи
    _private_key = None
    _public_key = None
    
    @classmethod
    def _log_jwt_operation(cls, operation: str, details: str = "", level: str = "info") -> None:
        """Унифицированное логирование операций с JWT"""
        log_method = getattr(logger, level.lower(), logger.info)
        border = "=" * 50
        log_method(f"\n{border}\nJWT {operation.upper()}\n{details}\n{border}")
    
    @classmethod
    def _generate_keys(cls) -> None:
        """Генерация RSA ключей с логированием."""
        if cls._private_key is None:
            start_time = time.time()
            try:
                cls._log_jwt_operation("Генерация RSA ключей")
                
                cls._private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=default_backend()
                )
                cls._public_key = cls._private_key.public_key()
                
                gen_time = (time.time() - start_time) * 1000
                cls._log_jwt_operation(
                    "RSA ключи сгенерированы",
                    f"Тип приватного ключа: {type(cls._private_key).__name__}\n"
                    f"Тип публичного ключа: {type(cls._public_key).__name__}\n"
                    f"Время генерации: {gen_time:.2f} мс"
                )
            except Exception as e:
                cls._log_jwt_operation(
                    "Ошибка генерации ключей",
                    f"Тип ошибки: {type(e).__name__}\n"
                    f"Сообщение: {str(e)}",
                    "error"
                )
                raise
    
    @classmethod
    def _get_private_key_pem(cls) -> bytes:
        """Получение приватного ключа в PEM формате с логированием."""
        cls._generate_keys()
        try:
            start_time = time.time()
            key_pem = cls._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            cls._log_jwt_operation(
                "Получен приватный ключ",
                f"Длина ключа: {len(key_pem)} байт\n"
                f"Время выполнения: {(time.time() - start_time) * 1000:.2f} мс",
                "debug"
            )
            return key_pem
        except Exception as e:
            cls._log_jwt_operation(
                "Ошибка получения приватного ключа",
                f"Тип ошибки: {type(e).__name__}\n"
                f"Сообщение: {str(e)}",
                "error"
            )
            raise
    
    @classmethod
    def _get_public_key_pem(cls) -> bytes:
        """Получение публичного ключа в PEM формате с логированием."""
        cls._generate_keys()
        try:
            start_time = time.time()
            key_pem = cls._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            cls._log_jwt_operation(
                "Получен публичный ключ",
                f"Длина ключа: {len(key_pem)} байт\n"
                f"Время выполнения: {(time.time() - start_time) * 1000:.2f} мс",
                "debug"
            )
            return key_pem
        except Exception as e:
            cls._log_jwt_operation(
                "Ошибка получения публичного ключа",
                f"Тип ошибки: {type(e).__name__}\n"
                f"Сообщение: {str(e)}",
                "error"
            )
            raise
    
    @classmethod
    def generate_tokens(cls, user_id: Union[str, int], algorithm: str = 'RS256') -> Dict[str, Union[str, int]]:
        """
        Генерация JWT токенов с детальным логированием.
        
        Параметры:
            user_id: Идентификатор пользователя
            algorithm: Алгоритм подписи (RS256/HS256)
            
        Возвращает:
            Словарь с access_token, refresh_token и метаданными
            
        Вызывает:
            Exception: При ошибках генерации токенов
        """
        start_time = time.time()
        try:
            user_id_str = str(user_id)
            cls._log_jwt_operation(
                "Начало генерации токенов",
                f"User ID: {user_id_str}\n"
                f"Алгоритм: {algorithm}\n"
                f"Access TTL: {cls._access_expires} сек\n"
                f"Refresh TTL: {cls._refresh_expires} сек"
            )
            
            # Формирование payload для токенов
            now = datetime.now(timezone.utc)
            access_payload = {
                'user_id': user_id_str,
                'exp': now + timedelta(seconds=cls._access_expires),
                'iat': now,
                'type': 'access',
                'alg': algorithm
            }
            
            refresh_payload = {
                'user_id': user_id_str,
                'exp': now + timedelta(seconds=cls._refresh_expires),
                'iat': now,
                'type': 'refresh',
                'alg': algorithm
            }
            
            # Выбор ключа в зависимости от алгоритма
            key = cls._get_private_key_pem() if algorithm == 'RS256' else cls._secret
            key_info = "RSA private key" if algorithm == 'RS256' else "HMAC secret"
            
            cls._log_jwt_operation(
                "Кодирование токенов",
                f"Используемый ключ: {key_info}\n"
                f"Access payload: {json.dumps(access_payload)}\n"
                f"Refresh payload: {json.dumps(refresh_payload)}",
                "debug"
            )
            
            # Генерация токенов
            access_token = jwt.encode(access_payload, key, algorithm=algorithm)
            refresh_token = jwt.encode(refresh_payload, key, algorithm=algorithm)
            
            # Формирование результата
            result = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': cls._access_expires,
                'algorithm': algorithm
            }
            
            cls._log_jwt_operation(
                "Токены успешно сгенерированы",
                f"Длина access token: {len(access_token)}\n"
                f"Длина refresh token: {len(refresh_token)}\n"
                f"Общее время: {(time.time() - start_time) * 1000:.2f} мс",
                "info"
            )
            
            return result
            
        except Exception as e:
            cls._log_jwt_operation(
                "Ошибка генерации токенов",
                f"User ID: {user_id_str}\n"
                f"Алгоритм: {algorithm}\n"
                f"Тип ошибки: {type(e).__name__}\n"
                f"Сообщение: {str(e)}\n"
                f"Время до ошибки: {(time.time() - start_time) * 1000:.2f} мс",
                "error"
            )
            raise
    
    @classmethod
    def _remove_old_sessions_if_needed(cls, user_id: Union[str, int]) -> Tuple[int, int]:
        """
        Удаление старых сессий при превышении лимита с детальным логированием.
        
        Возвращает:
            Tuple[int, int]: (удалено просроченных, удалено старых)
        """
        start_time = time.time()
        user_id_str = str(user_id)
        expired_deleted = 0
        old_deleted = 0
        
        try:
            cls._log_jwt_operation(
                "Проверка лимита сессий",
                f"User ID: {user_id_str}\n"
                f"Максимум сессий: {cls._max_sessions}"
            )
            
            with get_db_session() as session:
                # Удаление просроченных сессий
                result = session.execute(
                    text("DELETE FROM sessions WHERE user_id = :user_id AND expires_at <= NOW() RETURNING session_id"),
                    {'user_id': user_id_str}
                )
                expired_deleted = len(result.fetchall())
                
                # Проверка количества активных сессий
                active_count = session.execute(
                    text("SELECT COUNT(*) FROM sessions WHERE user_id = :user_id"),
                    {'user_id': user_id_str}
                ).scalar()
                
                # Удаление самых старых сессий при превышении лимита
                if active_count >= cls._max_sessions:
                    delete_count = active_count - cls._max_sessions + 1
                    cls._log_jwt_operation(
                        "Превышен лимит сессий",
                        f"Активных сессий: {active_count}\n"
                        f"Будет удалено: {delete_count}",
                        "warning"
                    )
                    
                    result = session.execute(
                        text("""
                            DELETE FROM sessions 
                            WHERE session_id IN (
                                SELECT session_id FROM sessions 
                                WHERE user_id = :user_id 
                                ORDER BY created_at ASC 
                                LIMIT :limit
                            ) RETURNING session_id
                        """),
                        {
                            'user_id': user_id_str,
                            'limit': delete_count
                        }
                    )
                    old_deleted = len(result.fetchall())
                    session.commit()
                
                cls._log_jwt_operation(
                    "Очистка сессий завершена",
                    f"Удалено просроченных: {expired_deleted}\n"
                    f"Удалено старых: {old_deleted}\n"
                    f"Общее время: {(time.time() - start_time) * 1000:.2f} мс"
                )
                
                return (expired_deleted, old_deleted)
                
        except Exception as e:
            cls._log_jwt_operation(
                "Ошибка очистки сессий",
                f"User ID: {user_id_str}\n"
                f"Тип ошибки: {type(e).__name__}\n"
                f"Сообщение: {str(e)}\n"
                f"Время до ошибки: {(time.time() - start_time) * 1000:.2f} мс",
                "error"
            )
            raise
    
    @classmethod
    def create_session(
        cls,
        user_id: Union[str, int],
        access_token: str,
        refresh_token: str,
        refresh_token_hash: str,
        user_agent: str,
        ip_address: str
    ) -> str:
        """
        Создание новой сессии с детальным логированием.
        
        Параметры:
            user_id: Идентификатор пользователя
            access_token: Access JWT токен
            refresh_token: Refresh JWT токен
            refresh_token_hash: Хеш refresh токена
            user_agent: User-Agent клиента
            ip_address: IP адрес клиента
            
        Возвращает:
            Идентификатор созданной сессии
            
        Вызывает:
            Exception: При ошибках создания сессии
        """
        start_time = time.time()
        user_id_str = str(user_id)
        
        try:
            cls._log_jwt_operation(
                "Создание новой сессии",
                f"User ID: {user_id_str}\n"
                f"User-Agent: {user_agent[:100]}...\n"
                f"IP: {ip_address}"
            )
            
            # Очистка старых сессий
            expired_deleted, old_deleted = cls._remove_old_sessions_if_needed(user_id_str)
            
            # Создание новой сессии
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=cls._refresh_expires)
            
            with get_db_session() as session:
                result = session.execute(
                    text("""
                        INSERT INTO sessions (
                            user_id, access_token, refresh_token_hash,
                            user_agent, ip_address, expires_at
                        ) VALUES (
                            :user_id, :access_token, :refresh_token_hash,
                            :user_agent, :ip_address, :expires_at
                        ) RETURNING session_id, created_at
                    """),
                    {
                        'user_id': user_id_str,
                        'access_token': access_token,
                        'refresh_token_hash': refresh_token_hash,
                        'user_agent': user_agent,
                        'ip_address': ip_address,
                        'expires_at': expires_at
                    }
                )
                session.commit()
                
                row = result.fetchone()
                session_id = str(row.session_id)
                created_at = row.created_at
                
                cls._log_jwt_operation(
                    "Сессия успешно создана",
                    f"Session ID: {session_id}\n"
                    f"Создана: {created_at}\n"
                    f"Истекает: {expires_at}\n"
                    f"Удалено сессий: {expired_deleted + old_deleted}\n"
                    f"Общее время: {(time.time() - start_time) * 1000:.2f} мс"
                )
                
                return session_id
                
        except Exception as e:
            cls._log_jwt_operation(
                "Ошибка создания сессии",
                f"User ID: {user_id_str}\n"
                f"Тип ошибки: {type(e).__name__}\n"
                f"Сообщение: {str(e)}\n"
                f"Время до ошибки: {(time.time() - start_time) * 1000:.2f} мс",
                "error"
            )
            raise