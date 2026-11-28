"""seed_canteen_menu_and_settings

Revision ID: 2a3b4c5d6e7f
Revises: 1db3e7f73949
Create Date: 2026-11-25 17:05:00.000000

"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from app.seed_data import DEMO_PRODUCTS

# revision identifiers, used by Alembic.
revision = '2a3b4c5d6e7f'
down_revision = '1db3e7f73949'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # Seed CanteenSettings if empty
    settings_count = conn.execute(sa.text("SELECT count(*) FROM canteen_settings")).scalar()
    if settings_count == 0:
        canteen_settings_table = sa.table(
            'canteen_settings',
            sa.column('id', sa.Integer),
            sa.column('is_accepting_orders', sa.Boolean),
            sa.column('payment_provider', sa.String),
            sa.column('merchant_display_name', sa.String),
            sa.column('upi_vpa', sa.String),
            sa.column('cash_enabled', sa.Boolean),
            sa.column('cash_max_order_paise', sa.Integer),
            sa.column('updated_at', sa.DateTime),
        )
        op.bulk_insert(canteen_settings_table, [{
            'id': 1,
            'is_accepting_orders': True,
            'payment_provider': 'sandbox',
            'merchant_display_name': 'TrayUP Canteen',
            'upi_vpa': 'canteen@ybl',
            'cash_enabled': False,
            'cash_max_order_paise': 20000,
            'updated_at': now,
        }])

    # Seed MenuItem catalog if empty
    menu_count = conn.execute(sa.text("SELECT count(*) FROM menu_items")).scalar()
    if menu_count == 0:
        menu_items_table = sa.table(
            'menu_items',
            sa.column('id', sa.Integer),
            sa.column('name', sa.String),
            sa.column('category', sa.String),
            sa.column('price_paise', sa.Integer),
            sa.column('description', sa.Text),
            sa.column('image_url', sa.String),
            sa.column('is_available', sa.Boolean),
            sa.column('reserved_quantity', sa.Integer),
            sa.column('created_at', sa.DateTime),
            sa.column('updated_at', sa.DateTime),
        )

        rows = [
            {
                'id': item['id'],
                'name': item['name'],
                'category': item['category'],
                'price_paise': item['price_paise'],
                'description': item['description'],
                'image_url': item['image_url'],
                'is_available': True,
                'reserved_quantity': 0,
                'created_at': now,
                'updated_at': now,
            }
            for item in DEMO_PRODUCTS
        ]
        op.bulk_insert(menu_items_table, rows)

        if conn.dialect.name == "postgresql":
            conn.execute(sa.text(
                "SELECT setval(pg_get_serial_sequence('menu_items', 'id'), COALESCE(MAX(id), 1)) FROM menu_items;"
            ))


def downgrade():
    pass
