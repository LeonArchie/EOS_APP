from flask import Flask
from k8s.healthz import healthz_bp
from k8s.readyz import readyz_bp

app = Flask(__name__)
app.register_blueprint(healthz_bp)
app.register_blueprint(readyz_bp)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)