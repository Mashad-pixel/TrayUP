"""seed_admin_user

Revision ID: 3b4c5d6e7f8a
Revises: 2a3b4c5d6e7f
Create Date: 2026-11-26 16:16:00.000000

"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from werkzeug.security import generate_password_hash

revision = '3b4c5d6e7f8a'
down_revision = '2a3b4c5d6e7f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # Check if admin already exists
    admin_exists = conn.execute(
        sa.text("SELECT count(*) FROM users WHERE email = 'admin@trayup.internal'")
    ).scalar()

    if admin_exists == 0:
        pwd_hash = generate_password_hash('AdminPass123!')
        conn.execute(sa.text("""
            INSERT INTO users (name, email, password_hash, role, is_active, created_at)
            VALUES ('Demo Admin', 'admin@trayup.internal', :pwd, 'ADMIN', true, :now)
        """), {'pwd': pwd_hash, 'now': now})

    # Kitchen staff account
    kitchen_exists = conn.execute(
        sa.text("SELECT count(*) FROM users WHERE email = 'kitchen@trayup.internal'")
    ).scalar()

    if kitchen_exists == 0:
        pwd_hash = generate_password_hash('KitchenPass123!')
        conn.execute(sa.text("""
            INSERT INTO users (name, email, password_hash, role, is_active, created_at)
            VALUES ('Demo Kitchen', 'kitchen@trayup.internal', :pwd, 'KITCHEN', true, :now)
        """), {'pwd': pwd_hash, 'now': now})


def downgrade():
    pass
