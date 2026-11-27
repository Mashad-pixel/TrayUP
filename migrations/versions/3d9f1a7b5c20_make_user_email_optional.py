"""make user email optional

Revision ID: 3d9f1a7b5c20
Revises: 2c8a4d6e0f11
Create Date: 2026-11-27 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3d9f1a7b5c20"
down_revision = "2c8a4d6e0f11"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=120),
            existing_nullable=False,
            nullable=True,
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=120),
            existing_nullable=True,
            nullable=False,
        )
