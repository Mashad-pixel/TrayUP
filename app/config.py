import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Used only for local development. create_app() refuses to start in production with it.
DEV_SECRET_KEY = "dev-only-change-me"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET_KEY)

    # Relative SQLite paths are stored in the instance/ folder by Flask-SQLAlchemy.
    _database_url = os.getenv("DATABASE_URL", "sqlite:///canteen.db")
    # Render Postgres may provide postgres://; normalize to SQLAlchemy's psycopg 3 driver.
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif _database_url.startswith("postgresql://"):
        _database_url = _database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    RATELIMIT_ENABLED = True
    # In-memory storage is fine locally. Use Redis in production (multiple workers share counts).
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    REGISTER_RATE_LIMIT = os.getenv("REGISTER_RATE_LIMIT", "20 per hour; 100 per day")

    ORDER_PAYMENT_EXPIRY_MINUTES = int(os.getenv("ORDER_PAYMENT_EXPIRY_MINUTES", "10"))
    COLLECTION_TOKEN_EXPIRY_MINUTES = int(os.getenv("COLLECTION_TOKEN_EXPIRY_MINUTES", "60"))

    # Canteen clock offset from UTC, used to group reports by local day (330 = India, UTC+05:30).
    CANTEEN_UTC_OFFSET_MINUTES = int(os.getenv("CANTEEN_UTC_OFFSET_MINUTES", "330"))

    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # Firebase Realtime Database is a server-side mirror for live order updates.
    FIREBASE_ENABLED = os.getenv("FIREBASE_ENABLED", "false").lower() == "true"
    FIREBASE_DATABASE_URL = os.getenv(
        "FIREBASE_DATABASE_URL",
        "https://trayup-36abb-default-rtdb.asia-southeast1.firebasedatabase.app/",
    )
    _firebase_service_account_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "serviceAccountKey.json",
    )
    if not os.path.isabs(_firebase_service_account_path):
        _firebase_service_account_path = os.path.join(BASE_DIR, _firebase_service_account_path)
    FIREBASE_SERVICE_ACCOUNT_PATH = os.path.abspath(_firebase_service_account_path)


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
    FIREBASE_ENABLED = False  # Unit tests never contact the live Firebase project.


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
