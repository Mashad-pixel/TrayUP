from flask import Flask, jsonify, request
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from app.responses import error_response
from app.cli import register_cli
from app.config import DEV_SECRET_KEY, config_map
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.models.user import User
from app.routes.admin import admin_bp
from app.routes.admin_orders import admin_orders_bp
from app.routes.admin_refunds import admin_refunds_bp
from app.routes.auth import auth_bp
from app.routes.frontend import frontend_bp
from app.routes.kitchen import kitchen_bp
from app.routes.orders import orders_bp
from app.routes.payments import payments_bp
from app.routes.public import public_bp
from app.routes.reports import reports_bp
from app.services.firebase_service import initialize_firebase


@login_manager.user_loader
def load_user(user_id):
    try:
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

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

    if config_name == "production":
        secret_key = app.config.get("SECRET_KEY")
        if not isinstance(secret_key, str) or len(secret_key) < 32 or secret_key == DEV_SECRET_KEY:
            raise RuntimeError(
                "Production requires a unique SECRET_KEY of at least 32 characters."
            )

    trusted_proxy_count = app.config.get("TRUSTED_PROXY_COUNT", 0)
    if trusted_proxy_count:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=trusted_proxy_count,
            x_proto=trusted_proxy_count,
        )

    db.init_app(app)
    initialize_firebase(app)
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
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(self)")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        response.vary.add("Cookie")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    limiter.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(frontend_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_orders_bp)
    app.register_blueprint(kitchen_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_refunds_bp)
    app.register_blueprint(reports_bp)

    register_cli(app)
    return app
