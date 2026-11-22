from flask import Blueprint, jsonify
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.services.canteen_service import get_status
from app.services.menu_service import list_public_menu_items, serialize_public_menu_item

public_bp = Blueprint("public", __name__, url_prefix="/api")


@public_bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(status="error", database="unavailable"), 503
    return jsonify(status="ok", database="ok"), 200


@public_bp.get("/csrf-token")
def csrf_token():
    response = jsonify(csrf_token=generate_csrf())
    response.headers["Cache-Control"] = "no-store"
    return response, 200


@public_bp.get("/menu")
def menu():
    items = list_public_menu_items()
    return jsonify(items=[serialize_public_menu_item(item) for item in items]), 200


@public_bp.get("/canteen/status")
def canteen_status():
    return jsonify(get_status()), 200
