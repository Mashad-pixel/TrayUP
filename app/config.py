import math
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Used only for local development. create_app() refuses to start in production with it.
DEV_SECRET_KEY = "dev-only-change-me"


def _optional_float(name):
    """Return the env value as a finite float, or None when it is unset or blank."""
    raw = os.getenv(name, "").strip()
    if raw == "":
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    return value


def _number_env(name, default, cast):
    raw = os.getenv(name, "").strip()
    if raw == "":
        return cast(default)
    try:
        value = cast(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive number.")
    return value


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET_KEY)

    # Relative SQLite paths are stored in the instance/ folder by Flask-SQLAlchemy.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///canteen.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    RATELIMIT_ENABLED = True
    # In-memory storage is fine locally. Use Redis in production (multiple workers share counts).
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    ORDER_PAYMENT_EXPIRY_MINUTES = int(os.getenv("ORDER_PAYMENT_EXPIRY_MINUTES", "10"))
    COLLECTION_TOKEN_EXPIRY_MINUTES = int(os.getenv("COLLECTION_TOKEN_EXPIRY_MINUTES", "60"))

    # Canteen clock offset from UTC, used to group reports by local day (330 = India, UTC+05:30).
    CANTEEN_UTC_OFFSET_MINUTES = int(os.getenv("CANTEEN_UTC_OFFSET_MINUTES", "330"))

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Live presence verification. Coordinates come only from the environment: never invent them.
    # When unset, ordering stays unavailable (fail closed); production refuses to start instead.
    CANTEEN_LATITUDE = _optional_float("CANTEEN_LATITUDE")
    CANTEEN_LONGITUDE = _optional_float("CANTEEN_LONGITUDE")
    PRESENCE_RADIUS_METERS = _number_env("PRESENCE_RADIUS_METERS", 100, float)
    PRESENCE_MAX_ACCURACY_METERS = _number_env("PRESENCE_MAX_ACCURACY_METERS", 75, float)
    PRESENCE_TOKEN_TTL_SECONDS = _number_env("PRESENCE_TOKEN_TTL_SECONDS", 10, int)
    PRESENCE_SESSION_TTL_SECONDS = _number_env("PRESENCE_SESSION_TTL_SECONDS", 180, int)
    PRESENCE_GPS_MAX_AGE_SECONDS = _number_env("PRESENCE_GPS_MAX_AGE_SECONDS", 60, int)
    PRESENCE_RETENTION_DAYS = _number_env("PRESENCE_RETENTION_DAYS", 7, int)

    # Public origin used to build the links inside the canteen QR code, for example https://trayup.example.
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip()


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    # Existing API tests remain focused; CSRF is explicitly enabled in security tests.
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"

    # Always empty in tests, even if .env has real keys, so tests never call Razorpay.
    RAZORPAY_KEY_ID = ""
    RAZORPAY_KEY_SECRET = ""
    RAZORPAY_WEBHOOK_SECRET = "test_webhook_secret"

    # Test-only fixture point at (0, 0). It is not a real canteen location.
    CANTEEN_LATITUDE = 0.0
    CANTEEN_LONGITUDE = 0.0
    PUBLIC_BASE_URL = "http://localhost"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def validate_runtime_settings(settings, config_name):
    """Fail closed on missing or unsafe presence configuration. Raises RuntimeError.

    `settings` is any mapping with the Config keys (app.config works). Kept free of Flask
    so it can be tested directly.
    """
    latitude = settings.get("CANTEEN_LATITUDE")
    longitude = settings.get("CANTEEN_LONGITUDE")

    if (latitude is None) != (longitude is None):
        raise RuntimeError("Set both CANTEEN_LATITUDE and CANTEEN_LONGITUDE, or neither.")

    if latitude is not None and not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise RuntimeError(
            "CANTEEN_LATITUDE must be between -90 and 90, and CANTEEN_LONGITUDE between -180 and 180."
        )

    if not (1 <= settings.get("PRESENCE_TOKEN_TTL_SECONDS", 10) <= 30):
        raise RuntimeError("PRESENCE_TOKEN_TTL_SECONDS must be between 1 and 30.")
    if not (30 <= settings.get("PRESENCE_SESSION_TTL_SECONDS", 180) <= 600):
        raise RuntimeError("PRESENCE_SESSION_TTL_SECONDS must be between 30 and 600.")

    if config_name == "production":
        if latitude is None:
            raise RuntimeError(
                "Set CANTEEN_LATITUDE and CANTEEN_LONGITUDE before running in production. "
                "Ordering cannot be verified without them."
            )
        base_url = settings.get("PUBLIC_BASE_URL") or ""
        if not base_url.startswith("https://"):
            raise RuntimeError("Set PUBLIC_BASE_URL to your https:// address before running in production.")
