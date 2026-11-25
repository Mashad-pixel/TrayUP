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

    # Payment provider & store settings
    payment_provider = db.Column(db.String(32), nullable=False, default="sandbox", server_default="sandbox")
    merchant_display_name = db.Column(db.String(100), nullable=False, default="TrayUP Canteen", server_default="TrayUP Canteen")
    upi_vpa = db.Column(db.String(100), nullable=True)
    cash_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    cash_max_order_paise = db.Column(db.Integer, nullable=False, default=15000, server_default="15000")

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
