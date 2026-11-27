"""add persistent menu categories (idempotent for historical branch reconciliation)"""
from alembic import op
import sqlalchemy as sa

revision = "2b3c4d5e6f70"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def _columns(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)} if sa.inspect(op.get_bind()).has_table(table) else set()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("menu_categories"):
        op.create_table(
            "menu_categories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=60), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_menu_categories_name"),
        )
    elif "sort_order" not in _columns("menu_categories"):
        with op.batch_alter_table("menu_categories") as batch_op:
            batch_op.add_column(sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False))
    op.execute(sa.text("""
        INSERT INTO menu_categories (name, sort_order, created_at, updated_at)
        SELECT DISTINCT mi.category, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM menu_items AS mi
        WHERE mi.category IS NOT NULL AND TRIM(mi.category) <> ''
          AND NOT EXISTS (SELECT 1 FROM menu_categories AS mc WHERE LOWER(mc.name) = LOWER(mi.category))
    """))


def downgrade():
    # The category table may also have been created by the parallel legacy revision.
    if sa.inspect(op.get_bind()).has_table("menu_categories"):
        op.drop_table("menu_categories")
