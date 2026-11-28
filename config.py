import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Local development only. Production refuses this fallback.
DEV_SECRET_KEY = "dev-only-change-me"  # nosec B105


def _positive_int_env(name, default):
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def validate_rate_limit_storage(config, environment):
    """Reject process-local rate-limit counters in production deployments."""
    uri = str(config.get("RATELIMIT_STORAGE_URI", "memory://"))
    raw_allow_memory = config.get("RATELIMIT_ALLOW_MEMORY", False)
    allow_memory = raw_allow_memory is True or str(raw_allow_memory).strip().lower() in {"1", "true", "yes", "on"}
    if str(environment).lower() == "production" and not uri.startswith(("redis://", "rediss://")) and not allow_memory:
        raise RuntimeError("Production requires a shared rate-limit store (Redis or another shared backend).")
    return True


def validate_runtime_settings(settings, environment):
    """Validate presence-verification settings before they can weaken runtime checks."""
    environment = str(environment).lower()
    latitude = settings.get("CANTEEN_LATITUDE")
    longitude = settings.get("CANTEEN_LONGITUDE")

    if environment == "production" and (latitude is None or longitude is None):
        if latitude is None and longitude is None:
            raise RuntimeError("CANTEEN_LATITUDE and CANTEEN_LONGITUDE are required in production.")
        raise RuntimeError("Set both CANTEEN_LATITUDE and CANTEEN_LONGITUDE.")
    if (latitude is None) != (longitude is None):
        raise RuntimeError("Set both CANTEEN_LATITUDE and CANTEEN_LONGITUDE.")

    if latitude is not None and longitude is not None:
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("CANTEEN_LATITUDE and CANTEEN_LONGITUDE must be numeric.") from exc
        if not -90 <= latitude <= 90:
            raise RuntimeError(
                "Coordinates must be within valid ranges: latitude between -90 and 90, "
                "longitude between -180 and 180."
            )
        if not -180 <= longitude <= 180:
            raise RuntimeError(
                "Coordinates must be within valid ranges: latitude between -90 and 90, "
                "longitude between -180 and 180."
            )

    if environment == "production":
        base_url = settings.get("PUBLIC_BASE_URL")
        if not isinstance(base_url, str) or not base_url.startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL must use https in production.")

    token_ttl = settings.get("PRESENCE_TOKEN_TTL_SECONDS")
    session_ttl = settings.get("PRESENCE_SESSION_TTL_SECONDS")
    if not isinstance(token_ttl, int) or not 1 <= token_ttl <= 30:
        raise RuntimeError("PRESENCE_TOKEN_TTL_SECONDS (TOKEN_TTL) must be between 1 and 30 seconds.")
    if not isinstance(session_ttl, int) or session_ttl <= token_ttl:
        raise RuntimeError("PRESENCE_SESSION_TTL_SECONDS (SESSION_TTL) must exceed TOKEN_TTL.")
    return True


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET_KEY)

    # Email for password-recovery codes. "smtp" sends real mail; "console" writes the message to
    # the log (development only); "memory" collects messages in tests.
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "smtp")
    MAIL_HOST = os.getenv("MAIL_HOST", "")
    MAIL_PORT = _positive_int_env("MAIL_PORT", 587)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"

    _database_url = os.getenv("DATABASE_URL", "sqlite:///canteen.db")
    # Normalize Render's Postgres URL to SQLAlchemy's psycopg 3 driver.
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif _database_url.startswith("postgresql://"):
        _database_url = _database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Bound request bodies (including webhook payloads) to reduce memory exhaustion risk.
    MAX_CONTENT_LENGTH = 1_048_576

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    # Longest a browser keeps the session cookie. The server enforces the real limits per
    # session (see the SESSION_* lifetimes below), so this is only an upper bound.
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Server-side session lifetimes. Privileged roles get short idle and absolute limits.
    SESSION_IDLE_MINUTES_PRIVILEGED = _positive_int_env("SESSION_IDLE_MINUTES_PRIVILEGED", 30)
    SESSION_ABSOLUTE_HOURS_PRIVILEGED = _positive_int_env("SESSION_ABSOLUTE_HOURS_PRIVILEGED", 8)
    SESSION_IDLE_MINUTES_STUDENT = _positive_int_env("SESSION_IDLE_MINUTES_STUDENT", 720)
    SESSION_ABSOLUTE_HOURS_STUDENT = _positive_int_env("SESSION_ABSOLUTE_HOURS_STUDENT", 168)

    # Administrator two-factor authentication: how long a password step stays valid while
    # the code is entered, and how many wrong codes lock the account for a while.
    MFA_PENDING_MINUTES = _positive_int_env("MFA_PENDING_MINUTES", 5)
    MFA_MAX_FAILED_ATTEMPTS = _positive_int_env("MFA_MAX_FAILED_ATTEMPTS", 5)
    MFA_LOCKOUT_MINUTES = _positive_int_env("MFA_LOCKOUT_MINUTES", 15)

    # Content-Security-Policy. Report-only is for rollout checks; production enforces.
    CSP_REPORT_ONLY = os.getenv("CSP_REPORT_ONLY", "false").lower() == "true"
    CSP_UPGRADE_INSECURE = False

    # Hosts that menu item images may be loaded from. Exact hostnames only.
    MENU_IMAGE_ALLOWED_HOSTS = [
        host.strip()
        for host in os.getenv("MENU_IMAGE_ALLOWED_HOSTS", "images.unsplash.com").split(",")
        if host.strip()
    ]

    RATELIMIT_ENABLED = True
    # For production with multiple workers/instances, configure a shared Redis store.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    # Off by default everywhere. Render sets RENDER=true on every service, so a default keyed to
    # that variable would silently allow process-local rate limits in production.
    RATELIMIT_ALLOW_MEMORY = os.getenv("RATELIMIT_ALLOW_MEMORY", "false").lower() == "true"
    REGISTER_RATE_LIMIT = os.getenv("REGISTER_RATE_LIMIT", "20 per hour; 100 per day")

    # Trust only the configured reverse-proxy count when interpreting forwarded client headers.
    TRUSTED_PROXY_COUNT = max(0, int(os.getenv("TRUSTED_PROXY_COUNT", "0")))

    ORDER_PAYMENT_EXPIRY_MINUTES = int(os.getenv("ORDER_PAYMENT_EXPIRY_MINUTES", "10"))
    # Unpaid orders this far past their payment window mean the expiry sweep has stalled.
    ORDER_EXPIRY_ALERT_MINUTES = int(os.getenv("ORDER_EXPIRY_ALERT_MINUTES", "15"))
    COLLECTION_TOKEN_EXPIRY_MINUTES = int(os.getenv("COLLECTION_TOKEN_EXPIRY_MINUTES", "60"))
    CANTEEN_UTC_OFFSET_MINUTES = int(os.getenv("CANTEEN_UTC_OFFSET_MINUTES", "330"))

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # No default location. A missing value is None, and production refuses to start (see
    # validate_runtime_settings). Defaulting to 0.0, 0.0 would put the geofence in the ocean.
    CANTEEN_LATITUDE = float(os.environ["CANTEEN_LATITUDE"]) if os.getenv("CANTEEN_LATITUDE") else None
    CANTEEN_LONGITUDE = float(os.environ["CANTEEN_LONGITUDE"]) if os.getenv("CANTEEN_LONGITUDE") else None
    PRESENCE_RADIUS_METERS = _positive_int_env("PRESENCE_RADIUS_METERS", 100)
    PRESENCE_MAX_ACCURACY_METERS = _positive_int_env("PRESENCE_MAX_ACCURACY_METERS", 75)
    PRESENCE_GPS_MAX_AGE_SECONDS = _positive_int_env("PRESENCE_GPS_MAX_AGE_SECONDS", 60)
    PRESENCE_TOKEN_TTL_SECONDS = _positive_int_env("PRESENCE_TOKEN_TTL_SECONDS", 10)
    PRESENCE_SESSION_TTL_SECONDS = _positive_int_env("PRESENCE_SESSION_TTL_SECONDS", 180)
    PRESENCE_RETENTION_DAYS = _positive_int_env("PRESENCE_RETENTION_DAYS", 30)
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL", "")

    RECOVERY_DELIVERY = os.getenv("RECOVERY_DELIVERY", "smtp")
    RECOVERY_CODE_MINUTES = _positive_int_env("RECOVERY_CODE_MINUTES", 5)
    RECOVERY_RESET_MINUTES = _positive_int_env("RECOVERY_RESET_MINUTES", 10)
    RECOVERY_RESEND_SECONDS = _positive_int_env("RECOVERY_RESEND_SECONDS", 30)
    RECOVERY_MAX_CODES_PER_HOUR = _positive_int_env("RECOVERY_MAX_CODES_PER_HOUR", 5)
    RECOVERY_MAX_ATTEMPTS = _positive_int_env("RECOVERY_MAX_ATTEMPTS", 5)
    ALLOW_CONSOLE_DELIVERY = os.getenv("ALLOW_CONSOLE_DELIVERY", "false").lower() == "true"
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = _positive_int_env("SMTP_PORT", 587)
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    PHONEPE_SALT_KEY = os.getenv("PHONEPE_SALT_KEY", "")
    PHONEPE_SALT_INDEX = os.getenv("PHONEPE_SALT_INDEX", "1")
    UPI_VPA = os.getenv("UPI_VPA", "")

    # Firebase project endpoint is deployment configuration, not source code.
    FIREBASE_ENABLED = os.getenv("FIREBASE_ENABLED", "false").lower() == "true"
    FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "").strip()
    _firebase_service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
    if not os.path.isabs(_firebase_service_account_path):
        _firebase_service_account_path = os.path.join(BASE_DIR, _firebase_service_account_path)
    FIREBASE_SERVICE_ACCOUNT_PATH = os.path.abspath(_firebase_service_account_path)


class DevelopmentConfig(Config):
    DEBUG = True
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console")


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"  # nosec B105
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"
    RAZORPAY_KEY_ID = ""
    RAZORPAY_KEY_SECRET = ""  # nosec B105 - intentionally empty in tests; never a usable credential.
    RAZORPAY_WEBHOOK_SECRET = "test_webhook_secret"  # nosec B105
    FIREBASE_ENABLED = False
    MAIL_BACKEND = "memory"
    RECOVERY_DELIVERY = "memory"
    CANTEEN_LATITUDE = 0.0
    CANTEEN_LONGITUDE = 0.0
    PHONEPE_SALT_KEY = "test_phonepe_salt_key_1234567890"
    UPI_VPA = "canteen@ybl"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    CSP_UPGRADE_INSECURE = True


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
