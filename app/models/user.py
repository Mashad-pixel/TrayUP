from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class UserRole:
    ADMIN = "ADMIN"
    KITCHEN = "KITCHEN"
    STUDENT = "STUDENT"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    mobile_number = db.Column(db.String(16), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=UserRole.STUDENT, index=True)

    # Overrides UserMixin.is_active. load_user() rejects inactive users.
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password, method="scrypt")

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)
