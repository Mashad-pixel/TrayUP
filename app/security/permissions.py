from functools import wraps

from flask_login import current_user

from app.responses import error_response


def roles_required(*allowed_roles):
    """Allow the request only if the logged-in user has one of the given roles.

    Anonymous callers get a 401 AUTH_REQUIRED here even if @login_required was forgotten, so
    this decorator never reads a role from an anonymous user. Callers should still place
    @login_required above it, which gives the same response.
    """
    if not allowed_roles:
        raise ValueError("roles_required needs at least one role.")

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return error_response("AUTH_REQUIRED", "Please log in first.", 401)
            if current_user.role not in allowed_roles:
                return error_response(
                    "FORBIDDEN",
                    "You do not have permission to do this.",
                    403,
                )
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
