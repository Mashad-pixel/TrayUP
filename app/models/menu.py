from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    __table_args__ = (
        db.CheckConstraint("price_paise >= 0", name="ck_menu_items_price_non_negative"),
        db.CheckConstraint(
            "stock_quantity IS NULL OR stock_quantity >= 0",
            name="ck_menu_items_stock_non_negative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(60), nullable=False, index=True)

    # Integer paise only (₹1 = 100 paise). Never use floats for money.
    price_paise = db.Column(db.Integer, nullable=False)

    image_url = db.Column(db.String(500), nullable=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True)

    # NULL means the item is not stock-tracked.
    stock_quantity = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
