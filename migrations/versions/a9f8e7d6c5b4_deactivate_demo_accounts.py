"""deactivate_demo_accounts

Revision ID: a9f8e7d6c5b4
Revises: 9a0b1c2d3e4f
Create Date: 2026-11-28 03:30:00.000000

Earlier revisions created two demo accounts with passwords published in the source code. This
deactivates each one only while its password hash still matches that published password, so a
database where someone already changed the password is left alone. Nothing is deleted, and the
downgrade does nothing: a deactivated demo account is never reactivated automatically.
"""
import sqlalchemy as sa
from alembic import op
from werkzeug.security import check_password_hash

revision = 'a9f8e7d6c5b4'
down_revision = '9a0b1c2d3e4f'
branch_labels = None
depends_on = None

DEMO_ACCOUNTS = (
    ("admin@trayup.internal", "AdminPass123!"),
    ("kitchen@trayup.internal", "KitchenPass123!"),
)


def upgrade():
    conn = op.get_bind()
    for email, published_password in DEMO_ACCOUNTS:
        row = conn.execute(
            sa.text("SELECT id, password_hash, is_active FROM users WHERE email = :email"),
            {"email": email},
        ).first()
        if row is None or not row.password_hash or not row.is_active:
            continue
        if check_password_hash(row.password_hash, published_password):
            conn.execute(sa.text("UPDATE users SET is_active = :inactive WHERE id = :id"),
                         {"inactive": False, "id": row.id})


def downgrade():
    pass
