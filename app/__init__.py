from flask import Flask, jsonify
from flask_wtf.csrf import CSRFError

from app.responses import error_response

from app.cli import register_cli
from app.config import DEV_SECRET_KEY, config_map, validate_runtime_settings
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.models.user import User
from app.routes.admin import admin_bp
from app.routes.admin_orders import admin_orders_bp
from app.routes.admin_refunds import admin_refunds_bp
from app.routes.auth import auth_bp
from app.routes.kitchen import kitchen_bp
from app.routes.frontend import frontend_bp
from app.routes.orders import orders_bp
from app.routes.payments import payments_bp
from app.routes.presence import presence_bp
from app.routes.public import public_bp
from app.routes.reports import reports_bp


@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

    # Deactivated staff or students lose access immediately.
    if user is None or not user.is_active:
        return None
    return user


@login_manager.unauthorized_handler
def unauthorized():
    return (
        jsonify({
            "success": False,
            "message": "Please log in first.",
            "error": {"code": "AUTH_REQUIRED"},
        }),
        401,
    )


def create_app(config_name="development"):
    if config_name not in config_map:
        raise ValueError(f"Unknown config '{config_name}'. Use: {', '.join(config_map)}.")

    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    if config_name == "production" and app.config["SECRET_KEY"] == DEV_SECRET_KEY:
        raise RuntimeError("Set a real SECRET_KEY in the environment before running in production.")

    # Fails closed: production will not start without canteen coordinates and an https PUBLIC_BASE_URL.
    validate_runtime_settings(app.config, config_name)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(exc):
        return error_response(
            "CSRF_TOKEN_INVALID",
            "The CSRF token is missing or invalid. Refresh the token and retry.",
            400,
        )

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
    limiter.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_orders_bp)
    app.register_blueprint(kitchen_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_refunds_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(presence_bp)
    app.register_blueprint(frontend_bp)

    register_cli(app)

    return app
