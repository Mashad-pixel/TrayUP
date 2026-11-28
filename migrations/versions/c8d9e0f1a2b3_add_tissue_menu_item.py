"""add Tissue menu item costing 1 rupee"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa


revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM menu_items WHERE name = :name"),
        {"name": "Tissue"},
    ).first()
    if existing is not None:
        return

    now = datetime.now(timezone.utc)
    menu_items_table = sa.table(
        "menu_items",
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("price_paise", sa.Integer),
        sa.column("description", sa.Text),
        sa.column("image_url", sa.String),
        sa.column("is_available", sa.Boolean),
        sa.column("is_veg", sa.Boolean),
        sa.column("reserved_quantity", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        menu_items_table,
        [
            {
                "name": "Tissue",
                "category": "Snacks",
                "price_paise": 100,
                "description": "Pack of clean paper tissues.",
                "image_url": "https://images.unsplash.com/photo-1583947215259-38e31be8751f?auto=format&fit=crop&w=900&q=82",
                "is_available": True,
                "is_veg": True,
                "reserved_quantity": 0,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('menu_items', 'id'), COALESCE(MAX(id), 1)) FROM menu_items;"
            )
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM menu_items WHERE name = :name"), {"name": "Tissue"})
