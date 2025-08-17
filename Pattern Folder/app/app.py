from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": True}), 200

@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({"status": "healthy"}), 200

@app.route('/readyz', methods=['GET'])
def readyz():
    return jsonify({"status": "ready"}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)