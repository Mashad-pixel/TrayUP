from datetime import datetime, time, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class CanteenSettings(db.Model):
    """Singleton settings row controlling ordering and public canteen details."""

    __tablename__ = "canteen_settings"
    __table_args__ = (db.CheckConstraint("id = 1", name="ck_canteen_settings_singleton"),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    is_accepting_orders = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    closed_message = db.Column(db.String(200), nullable=True)
    canteen_name = db.Column(db.String(120), nullable=False, default="TrayUP Canteen", server_default="TrayUP Canteen")
    opens_at = db.Column(db.Time, nullable=False, default=time(8, 0), server_default="08:00:00")
    closes_at = db.Column(db.Time, nullable=False, default=time(18, 0), server_default="18:00:00")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
