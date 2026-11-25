from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, limiter
from app.models.user import User, UserRole
from app.security.account_rules import is_valid_email, is_valid_name, normalize_email, password_problem

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



def email_unavailable_response():
    return error_response(
        "EMAIL_UNAVAILABLE",
        "An account with this email already exists. Try logging in instead.",
        409,
    )


@auth_bp.route("/register", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("REGISTER_RATE_LIMIT", "20 per hour; 100 per day"))
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")

    # The browser cannot choose a privileged role.
    if not isinstance(name, str) or not isinstance(email, str) or not isinstance(password, str):
        return error_response("INVALID_REGISTRATION", "Name, email and password are required.", 400)

    name = name.strip()
    email = normalize_email(email)

    if not is_valid_name(name):
        return error_response("INVALID_REGISTRATION", "Enter your name (up to 100 characters).", 400)
    if not is_valid_email(email):
        return error_response("INVALID_REGISTRATION", "Enter a valid email address.", 400)

    problem = password_problem(password)
    if problem:
        return error_response("INVALID_REGISTRATION", problem, 400)

    if User.query.filter_by(email=email).first() is not None:
        return email_unavailable_response()

    user = User(name=name, email=email, role=UserRole.STUDENT, is_active=True)
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        # The unique email constraint handles concurrent duplicate registrations.
        db.session.rollback()
        return email_unavailable_response()

    session.clear()
    login_user(user)
    data = serialize_user(user)
    data["csrf_token"] = generate_csrf()
    return success_response("Account created", data, status=201)
