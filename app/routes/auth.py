from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.models.user import User, UserRole
from app.security.account_rules import (
    is_valid_name,
    normalize_mobile_number,
    password_problem,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Keep credential-check timing similar for unknown identifiers.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def success_response(message, data=None, status=200):
    return jsonify({"success": True, "message": message, "data": data or {}}), status


def error_response(code, message, status):
    return (
        jsonify({"success": False, "message": message, "error": {"code": code}}),
        status,
    )


def invalid_credentials_response():
    return error_response("INVALID_CREDENTIALS", "Invalid credentials.", 401)


def serialize_user(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "mobile_number": user.mobile_number,
        "role": user.role,
    }


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    mobile_number = payload.get("mobile")
    email = payload.get("email")
    password = payload.get("password")

    if not isinstance(password, str) or not password:
        return error_response("MISSING_FIELDS", "A password is required.", 400)

    if mobile_number is not None:
        mobile_number = normalize_mobile_number(mobile_number)
        if not mobile_number:
            return error_response("INVALID_MOBILE", "Enter a valid mobile number.", 400)
        user = User.query.filter_by(mobile_number=mobile_number).first()
        if user is not None and user.role != UserRole.STUDENT:
            user = None
    else:
        if not isinstance(email, str) or not email.strip():
            return error_response("MISSING_FIELDS", "An email or mobile number is required.", 400)
        user = User.query.filter_by(email=email.strip().lower()).first()
        if user is not None and user.role == UserRole.STUDENT:
            user = None

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



def mobile_unavailable_response():
    return error_response(
        "MOBILE_UNAVAILABLE",
        "An account with this mobile number already exists.",
        409,
    )


@auth_bp.route("/register", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("REGISTER_RATE_LIMIT", "20 per hour; 100 per day"))
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    name = payload.get("name")
    mobile_number = payload.get("mobile")
    password = payload.get("password")

    # The browser cannot choose a privileged role.
    if not all(isinstance(value, str) for value in (name, mobile_number, password)):
        return error_response(
            "INVALID_REGISTRATION",
            "Name, mobile number and password are required.",
            400,
        )

    name = name.strip()
    mobile_number = normalize_mobile_number(mobile_number)

    if not is_valid_name(name):
        return error_response("INVALID_REGISTRATION", "Enter your name (up to 100 characters).", 400)
    if not mobile_number:
        return error_response("INVALID_REGISTRATION", "Enter a valid mobile number.", 400)

    problem = password_problem(password)
    if problem:
        return error_response("INVALID_REGISTRATION", problem, 400)

    if User.query.filter_by(mobile_number=mobile_number).first() is not None:
        return mobile_unavailable_response()

    user = User(
        name=name,
        mobile_number=mobile_number,
        role=UserRole.STUDENT,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if User.query.filter_by(mobile_number=mobile_number).first() is not None:
            return mobile_unavailable_response()
        raise

    session.clear()
    login_user(user)
    data = serialize_user(user)
    data["csrf_token"] = generate_csrf()
    return success_response("Account created", data, status=201)
