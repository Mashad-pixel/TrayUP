import os

from flask import Blueprint, send_from_directory

frontend_bp = Blueprint("frontend", __name__)

# The static HTML/CSS/JS lives in the repository's frontend/ folder, one level above app/.
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))


@frontend_bp.route("/frontend/<path:filename>", methods=["GET"])
def serve_frontend(filename):
    # send_from_directory rejects paths that escape FRONTEND_DIR (for example ../app/config.py).
    return send_from_directory(FRONTEND_DIR, filename)
