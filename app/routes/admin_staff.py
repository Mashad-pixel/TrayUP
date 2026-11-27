"""Staff accounts (ADMIN and KITCHEN), managed by administrators.

Students are managed through registration only. This API can never create, edit or disable
a student account. Every change that affects access ends that account's live sessions.

Validation errors name the offending field in `details`, which the admin pages show beside it.
"""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User, UserRole
from app.responses import error_response, success_response
from app.security.account_rules import (
    is_valid_email,
    is_valid_name,
    normalize_email,
    password_problem,
)
from app.security.permissions import roles_required
from app.services.session_service import revoke_user_sessions

admin_staff_bp = Blueprint("admin_staff", __name__, url_prefix="/api/admin/staff")

STAFF_ROLES = (UserRole.ADMIN, UserRole.KITCHEN)
UPDATABLE_FIELDS = frozenset({"name", "role", "is_active", "password"})
ROLE_MESSAGE = "Role must be ADMIN or KITCHEN."


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _serialize(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _staff_query():
    return User.query.filter(User.role.in_(STAFF_ROLES))


def _validation_error(details, message):
    """400 response with one message per offending field.

    An invalid role is reported as INVALID_ROLE; any other field problem is INVALID_STAFF.
    """
    code = "INVALID_ROLE" if set(details) == {"role"} else "INVALID_STAFF"
    response, status = error_response(code, message, 400)
    payload = response.get_json()
    payload["details"] = details
    return jsonify(payload), status


def _parse_role(raw):
    """Accept ADMIN or KITCHEN in any letter case. Returns the canonical value, or None."""
    if not isinstance(raw, str):
        return None
    role = raw.strip().upper()
    return role if role in STAFF_ROLES else None


def _audit(action, target, actor, **details):
    current_app.logger.info(
        "staff %s: target=%s actor=%s %s",
        action, target.id, actor.id,
        " ".join(f"{key}={value}" for key, value in sorted(details.items())),
    )


def _staff_response(message, row, status=200):
    """The record is returned under `data`, and also as top-level `staff` for older clients."""
    response, status = success_response(message, row, status=status)
    payload = response.get_json()
    payload["staff"] = row
    return jsonify(payload), status


@admin_staff_bp.get("")
@login_required
@roles_required(UserRole.ADMIN)
def list_staff():
    rows = [_serialize(user) for user in _staff_query().order_by(User.name, User.id).all()]
    response, status = success_response("Staff retrieved", {"staff": rows})
    payload = response.get_json()
    payload["staff"] = rows
    return jsonify(payload), status


@admin_staff_bp.post("")
@login_required
@roles_required(UserRole.ADMIN)
def create_staff():
    payload = _json_object()
    if payload is None:
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    missing = {
        field: "This field is required."
        for field in ("name", "email", "password", "role")
        if not isinstance(payload.get(field), str)
    }
    if missing:
        return _validation_error(missing, "Name, email, role and password are required.")

    name = " ".join(payload["name"].split())
    email = normalize_email(payload["email"])
    password = payload["password"]

    errors = {}
    if not is_valid_name(name):
        errors["name"] = "Enter a name (up to 100 characters)."
    if not is_valid_email(email):
        errors["email"] = "Enter a valid email address."
    role = _parse_role(payload["role"])
    if role is None:
        errors["role"] = ROLE_MESSAGE
    problem = password_problem(password)
    if problem:
        errors["password"] = problem
    if errors:
        return _validation_error(errors, "Staff account is invalid.")

    if User.query.filter_by(email=email).first() is not None:
        return error_response("EMAIL_UNAVAILABLE", "An account with this email already exists.", 409)

    user = User(name=name, email=email, role=role, is_active=True)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        # Another request created the same email between the check above and this insert.
        db.session.rollback()
        return error_response("EMAIL_UNAVAILABLE", "An account with this email already exists.", 409)

    _audit("created", user, current_user, role=role)
    return _staff_response("Staff account created", _serialize(user), status=201)


@admin_staff_bp.patch("/<int:user_id>")
@login_required
@roles_required(UserRole.ADMIN)
def update_staff(user_id):
    user = _staff_query().filter(User.id == user_id).with_for_update().first()
    if user is None:
        return error_response("STAFF_NOT_FOUND", "Staff account not found.", 404)

    payload = _json_object()
    if payload is None:
        return error_response("INVALID_JSON", "Request body must be a JSON object.", 400)

    unknown = sorted(set(payload) - UPDATABLE_FIELDS)
    if unknown:
        return error_response("INVALID_STAFF", f"Unsupported fields: {', '.join(unknown)}.", 400)
    if not payload:
        return error_response("INVALID_STAFF", "Provide a field to update.", 400)

    errors = {}
    new_name = user.name
    if "name" in payload:
        cleaned = " ".join(payload["name"].split()) if isinstance(payload["name"], str) else ""
        if is_valid_name(cleaned):
            new_name = cleaned
        else:
            errors["name"] = "Enter a name (up to 100 characters)."

    new_role = user.role
    if "role" in payload:
        parsed = _parse_role(payload["role"])
        if parsed is None:
            errors["role"] = ROLE_MESSAGE
        else:
            new_role = parsed

    new_active = user.is_active
    if "is_active" in payload:
        if isinstance(payload["is_active"], bool):
            new_active = payload["is_active"]
        else:
            errors["is_active"] = "Must be true or false."

    if "password" in payload:
        if not isinstance(payload["password"], str):
            errors["password"] = "Password must be text."
        else:
            problem = password_problem(payload["password"])
            if problem:
                errors["password"] = problem
    if errors:
        return _validation_error(errors, "Staff update is invalid.")

    # Stop an administrator from removing their own access. Everyone else can be changed,
    # because the acting administrator stays active.
    removes_own_admin_access = user.id == current_user.id and (
        new_role != UserRole.ADMIN or not new_active
    )
    if removes_own_admin_access:
        return error_response("SELF_LOCKOUT", "You cannot remove your own admin access.", 409)

    was_active_admin = user.role == UserRole.ADMIN and user.is_active
    remains_active_admin = new_role == UserRole.ADMIN and new_active
    if was_active_admin and not remains_active_admin:
        other_active_admins = User.query.filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
            User.id != user.id,
        ).count()
        if other_active_admins == 0:
            return error_response("LAST_ADMIN", "At least one active administrator must remain.", 409)

    access_changed = new_role != user.role or new_active != user.is_active
    password_changed = "password" in payload

    user.name = new_name
    user.role = new_role
    user.is_active = new_active
    if password_changed:
        user.set_password(payload["password"])
    db.session.commit()

    if access_changed or password_changed:
        # Role, status or password changed: end every live session so the new rules apply now.
        revoke_user_sessions(user.id)

    _audit(
        "updated", user, current_user,
        role=new_role, active=new_active, password_changed=password_changed,
    )
    return _staff_response("Staff account updated", _serialize(user))
