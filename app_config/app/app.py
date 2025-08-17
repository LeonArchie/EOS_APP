# app.py
from flask import Flask
from k8s.healthz import healthz_bp
from k8s.readyz import readyz_bp
from api.create.config_create import config_bp 

app = Flask(__name__)
app.register_blueprint(healthz_bp)
app.register_blueprint(readyz_bp)
app.register_blueprint(config_bp)  # Регистрируем новый blueprint

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)