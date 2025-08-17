from flask import Blueprint, jsonify

readyz_bp = Blueprint('readyz', __name__)

@readyz_bp.route('/readyz', methods=['GET'])
def readyz():
    return jsonify({"status": "ready"}), 200