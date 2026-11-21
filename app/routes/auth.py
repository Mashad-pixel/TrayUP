from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import limiter
from app.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Checked when the email doesn't exist, so response time doesn't reveal which emails are registered.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def success_response(message, data=None, status=200):
    return jsonify({"success": True, "message": message, "data": data or {}}), status


def error_response(code, message, status):
    return (
        jsonify({"success": False, "message": message, "error": {"code": code}}),
        status,
    )


def invalid_credentials_response():
    # Same message whether the email is unknown, the password is wrong, or the account is disabled.
    return error_response("INVALID_CREDENTIALS", "Invalid email or password.", 401)


def serialize_user(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    email = payload.get("email")
    password = payload.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return error_response("MISSING_FIELDS", "Email and password are required.", 400)

    email = email.strip().lower()
    if not email or not password:
        return error_response("MISSING_FIELDS", "Email and password are required.", 400)

    user = User.query.filter_by(email=email).first()

    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        return invalid_credentials_response()

    if not user.check_password(password) or not user.is_active:
        return invalid_credentials_response()

    # Clear any old session data before logging in, to prevent session fixation.
    session.clear()
    login_user(user)

    return success_response("Logged in successfully", serialize_user(user))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return success_response("Logged out successfully")


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return success_response("Current user", serialize_user(current_user))
