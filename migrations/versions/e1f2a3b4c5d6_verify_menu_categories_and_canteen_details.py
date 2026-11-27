"""final category/settings schema verification; safe for existing installs"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "3f9a1c2b4d5e"
branch_labels = None
depends_on = None


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
    else:
        columns = {column["name"] for column in inspector.get_columns("menu_categories")}
        if "sort_order" not in columns:
            with op.batch_alter_table("menu_categories") as batch_op:
                batch_op.add_column(sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False))
    op.execute(sa.text("""
        INSERT INTO menu_categories (name, sort_order, created_at, updated_at)
        SELECT DISTINCT mi.category, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM menu_items AS mi
        WHERE mi.category IS NOT NULL AND TRIM(mi.category) <> ''
          AND NOT EXISTS (SELECT 1 FROM menu_categories AS mc WHERE LOWER(mc.name) = LOWER(mi.category))
    """))
    columns = {column["name"] for column in sa.inspect(bind).get_columns("canteen_settings")}
    with op.batch_alter_table("canteen_settings", schema=None) as batch_op:
        if "canteen_name" not in columns:
            batch_op.add_column(sa.Column("canteen_name", sa.String(length=120), nullable=False, server_default="TrayUP Canteen"))
        if "opens_at" not in columns:
            batch_op.add_column(sa.Column("opens_at", sa.Time(), nullable=False, server_default="08:00:00"))
        if "closes_at" not in columns:
            batch_op.add_column(sa.Column("closes_at", sa.Time(), nullable=False, server_default="18:00:00"))


def downgrade():
    # Deliberately a no-op: this branch duplicates schema managed by the canonical revisions.
    pass
