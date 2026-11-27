"""add mobile number to users

Revision ID: 2c8a4d6e0f11
Revises: 1db3e7f73949
Create Date: 2026-11-27 15:14:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2c8a4d6e0f11"
down_revision = "1db3e7f73949"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mobile_number", sa.String(length=16), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_users_mobile_number"),
            ["mobile_number"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_mobile_number"))
        batch_op.drop_column("mobile_number")
