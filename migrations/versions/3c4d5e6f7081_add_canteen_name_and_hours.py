"""add canteen name and operating hours (idempotent for historical branch reconciliation)"""
from alembic import op
import sqlalchemy as sa

revision = "3c4d5e6f7081"
down_revision = "2b3c4d5e6f70"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("canteen_settings")}
    with op.batch_alter_table("canteen_settings", schema=None) as batch_op:
        if "canteen_name" not in columns:
            batch_op.add_column(sa.Column("canteen_name", sa.String(length=120), nullable=False, server_default="TrayUP Canteen"))
        if "opens_at" not in columns:
            batch_op.add_column(sa.Column("opens_at", sa.Time(), nullable=False, server_default="08:00:00"))
        if "closes_at" not in columns:
            batch_op.add_column(sa.Column("closes_at", sa.Time(), nullable=False, server_default="18:00:00"))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("canteen_settings")}
    with op.batch_alter_table("canteen_settings", schema=None) as batch_op:
        for name in ("closes_at", "opens_at", "canteen_name"):
            if name in columns:
                batch_op.drop_column(name)
