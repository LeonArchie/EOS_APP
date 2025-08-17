from flask import Blueprint, jsonify

healthz_bp = Blueprint('healthz', __name__)

@healthz_bp.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({"status": "healthy"}), 200