# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

import json
from flask import request
from maintenance.logger import setup_logger

logger = setup_logger(__name__)

def _filter_sensitive_data(headers):
    """Фильтрация чувствительных данных из заголовков"""
    sensitive_keys = ['authorization', 'cookie', 'token']
    return {k: '***FILTERED***' if k.lower() in sensitive_keys else v 
            for k, v in headers.items()}

def log_request_info():
    """Логирование входящего запроса"""
    filtered_headers = _filter_sensitive_data(dict(request.headers))
    logger.info(
        f"Incoming request: {request.method} {request.path}\n"
        f"From: {request.remote_addr}\n"
        f"Headers: {filtered_headers}\n"
        f"Query: {dict(request.args)}"
    )

def log_request_response(response):
    """Логирование ответа"""
    try:
        filtered_headers = _filter_sensitive_data(dict(request.headers))
        log_message = (
            f"{request.method} {request.path} - {response.status_code}\n"
            f"From: {request.remote_addr}\n"
            f"Headers: {filtered_headers}\n"
            f"Query: {dict(request.args)}"
        )

        if request.content_type not in ['multipart/form-data', 'application/octet-stream']:
            try:
                if request.data:
                    request_body = request.get_json(silent=True) or request.data.decode('utf-8')
                    log_message += f"\nRequest Body: {request_body}"
            except Exception as e:
                log_message += f"\nRequest Body Error: {str(e)}"

        try:
            if response.content_type == 'application/json':
                log_message += f"\nResponse Body: {json.loads(response.get_data(as_text=True))}"
            elif 'text/' in response.content_type:
                log_message += f"\nResponse Body: {response.get_data(as_text=True)}"
        except Exception as e:
            log_message += f"\nResponse Body Error: {str(e)}"

        logger.info(log_message)
    except Exception as e:
        logger.error(f"Failed to log request/response: {str(e)}", exc_info=True)

    return response