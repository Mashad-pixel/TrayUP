"""add customer checkout details and idempotency request fingerprint"""
from alembic import op
import sqlalchemy as sa

revision = "3f9a1c2b4d5e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("orders")}
    with op.batch_alter_table("orders", schema=None) as batch_op:
        for name, column in (
            ("customer_name", sa.Column("customer_name", sa.String(length=100), nullable=True)),
            ("customer_phone", sa.Column("customer_phone", sa.String(length=20), nullable=True)),
            ("instructions", sa.Column("instructions", sa.String(length=500), nullable=True)),
            ("request_fingerprint", sa.Column("request_fingerprint", sa.String(length=64), nullable=True)),
        ):
            if name not in columns:
                batch_op.add_column(column)


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("orders")}
    with op.batch_alter_table("orders", schema=None) as batch_op:
        for name in ("request_fingerprint", "instructions", "customer_phone", "customer_name"):
            if name in columns:
                batch_op.drop_column(name)
