from app.extensions import db
from app.models.order import utcnow


class MenuCategory(db.Model):
    """Persistent menu category. Menu items retain the category name for compatibility."""

    __tablename__ = "menu_categories"
    __table_args__ = (db.UniqueConstraint("name", name="uq_menu_categories_name"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
