"""add users.password_changed_at (guarded, safe on databases that already have it)"""
from alembic import op
import sqlalchemy as sa

revision = "6a7b8c9d0e1f"
down_revision = "8a9b0c1d2e3f"
branch_labels = None
depends_on = None


def _columns(table):
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)} if inspector.has_table(table) else set()


def upgrade():
    if "password_changed_at" not in _columns("users"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if "password_changed_at" in _columns("users"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("password_changed_at")
