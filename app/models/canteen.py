from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class CanteenSettings(db.Model):
    """Singleton settings row controlling whether new orders may be placed."""

    __tablename__ = "canteen_settings"
    __table_args__ = (
        db.CheckConstraint("id = 1", name="ck_canteen_settings_singleton"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    is_accepting_orders = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    closed_message = db.Column(db.String(200), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
