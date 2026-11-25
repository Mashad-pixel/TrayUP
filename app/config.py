import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Local development only. Production refuses this fallback.
DEV_SECRET_KEY = "dev-only-change-me"  # nosec B105


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET_KEY)

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

    RATELIMIT_ENABLED = True
    # For production with multiple workers/instances, configure a shared Redis store.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    REGISTER_RATE_LIMIT = os.getenv("REGISTER_RATE_LIMIT", "20 per hour; 100 per day")

    # Trust only the configured reverse-proxy count when interpreting forwarded client headers.
    TRUSTED_PROXY_COUNT = max(0, int(os.getenv("TRUSTED_PROXY_COUNT", "0")))

    ORDER_PAYMENT_EXPIRY_MINUTES = int(os.getenv("ORDER_PAYMENT_EXPIRY_MINUTES", "10"))
    COLLECTION_TOKEN_EXPIRY_MINUTES = int(os.getenv("COLLECTION_TOKEN_EXPIRY_MINUTES", "60"))
    CANTEEN_UTC_OFFSET_MINUTES = int(os.getenv("CANTEEN_UTC_OFFSET_MINUTES", "330"))

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Universal Payment & PhonePe Settings
    PAYMENT_DEFAULT_PROVIDER = os.getenv("PAYMENT_DEFAULT_PROVIDER", "sandbox")
    PAYMENT_SANDBOX_ENABLED = os.getenv("PAYMENT_SANDBOX_ENABLED", "true").lower() == "true"
    CANTEEN_UPI_VPA = os.getenv("CANTEEN_UPI_VPA", "")
    CANTEEN_MERCHANT_NAME = os.getenv("CANTEEN_MERCHANT_NAME", "TrayUP Canteen")
    PHONEPE_MERCHANT_ID = os.getenv("PHONEPE_MERCHANT_ID", "")
    PHONEPE_SALT_KEY = os.getenv("PHONEPE_SALT_KEY", "")
    PHONEPE_SALT_INDEX = os.getenv("PHONEPE_SALT_INDEX", "1")
    PHONEPE_ENV = os.getenv("PHONEPE_ENV", "UAT")

    # Firebase project endpoint is deployment configuration, not source code.
    FIREBASE_ENABLED = os.getenv("FIREBASE_ENABLED", "false").lower() == "true"
    FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "").strip()
    _firebase_service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
    if not os.path.isabs(_firebase_service_account_path):
        _firebase_service_account_path = os.path.join(BASE_DIR, _firebase_service_account_path)
    FIREBASE_SERVICE_ACCOUNT_PATH = os.path.abspath(_firebase_service_account_path)


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"  # nosec B105
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"
    RAZORPAY_KEY_ID = ""
    RAZORPAY_KEY_SECRET = ""
    RAZORPAY_WEBHOOK_SECRET = "test_webhook_secret"  # nosec B105
    FIREBASE_ENABLED = False
    PAYMENT_SANDBOX_ENABLED = True
    PHONEPE_MERCHANT_ID = "PGTESTPAYUAT"
    PHONEPE_SALT_KEY = "test_phonepe_salt_key_1234567890"  # nosec B105
    PHONEPE_SALT_INDEX = "1"
    CANTEEN_UPI_VPA = "testcanteen@ybl"
    CANTEEN_MERCHANT_NAME = "TrayUP Test Canteen"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PAYMENT_SANDBOX_ENABLED = os.getenv("PAYMENT_SANDBOX_ENABLED", "false").lower() == "true"


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
