# SPDX-License-Identifier: AGPL-3.0-only WITH LICENSE-ADDITIONAL
# Copyright (C) 2025 Петунин Лев Михайлович

from maintenance.read_config import config

def get_app_config():
    """Возвращает конфигурацию Flask-приложения"""
    return {
        'SECRET_KEY': config.get('app.flask_key', 'default-secret-key'),
        'VERSION': config.get('version', '0.0.0'),
        'SQLALCHEMY_DATABASE_URI': f"postgresql://{config.get('db.user')}:{config.get('db.password')}@{config.get('db.master_host')}:{config.get('db.master_port')}/{config.get('db.database')}",
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    }