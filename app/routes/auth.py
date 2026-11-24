import re

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.models.user import User, UserRole

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

REGISTRATION_NAME_MAX = 100
REGISTRATION_EMAIL_MAX = 120
REGISTRATION_PASSWORD_MIN = 8
REGISTRATION_PASSWORD_MAX = 128
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

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

    # login clears the session, which also drops the old CSRF token. Return a new one so the
    # frontend can keep making POST requests without an extra round trip.
    data = serialize_user(user)
    data["csrf_token"] = generate_csrf()
    return success_response("Logged in successfully", data)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return success_response("Logged out successfully", {"csrf_token": generate_csrf()})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return success_response("Current user", serialize_user(current_user))


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per 10 minutes")
def register_student():
    """Self-service student accounts. The role is always STUDENT; staff accounts come from the CLI."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")

    if not isinstance(name, str) or not isinstance(email, str) or not isinstance(password, str):
        return error_response("INVALID_REGISTRATION", "Name, email and password are required.", 400)

    name = name.strip()
    email = email.strip().lower()

    if not name or len(name) > REGISTRATION_NAME_MAX:
        return error_response("INVALID_REGISTRATION", f"Name must be 1 to {REGISTRATION_NAME_MAX} characters.", 400)
    if len(email) > REGISTRATION_EMAIL_MAX or not _EMAIL_PATTERN.match(email):
        return error_response("INVALID_REGISTRATION", "Enter a valid email address.", 400)
    if not (REGISTRATION_PASSWORD_MIN <= len(password) <= REGISTRATION_PASSWORD_MAX):
        return error_response(
            "INVALID_REGISTRATION",
            f"Password must be {REGISTRATION_PASSWORD_MIN} to {REGISTRATION_PASSWORD_MAX} characters.",
            400,
        )

    user = User(name=name, email=email, role=UserRole.STUDENT, is_active=True)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("EMAIL_UNAVAILABLE", "An account with this email already exists. Log in instead.", 409)

    # Same session hygiene as login: clear any old session, then sign in and issue a CSRF token.
    session.clear()
    login_user(user)

    data = serialize_user(user)
    data["csrf_token"] = generate_csrf()
    return success_response("Account created", data, 201)
