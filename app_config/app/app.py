# app.py
from flask import Flask
from k8s.healthz import healthz_bp
from k8s.readyz import readyz_bp
from api.create.config_create import config_bp
from maintenance.logging_config import setup_logging

app = Flask(__name__)
logger = setup_logging()
logger.info("Приложение запускается")

app.register_blueprint(healthz_bp)
app.register_blueprint(readyz_bp)
app.register_blueprint(config_bp)

if __name__ == '__main__':
    logger.info("Сервер запущен на 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)