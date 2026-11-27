"""add active password recovery tables; idempotent with legacy recovery revision"""
from alembic import op
import sqlalchemy as sa

revision = "5e6f7a8b9c0d"
down_revision = "4d9e1f2a3b5c"
branch_labels = None
depends_on = None


def _has_table(name): return sa.inspect(op.get_bind()).has_table(name)
def _indexes(name): return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(name)} if _has_table(name) else set()


def upgrade():
    if not _has_table("otp_challenges"):
        op.create_table("otp_challenges", sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("purpose", sa.String(length=20), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False), sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"))
    indexes = _indexes("otp_challenges")
    for name, col in (("ix_otp_challenges_user_id", "user_id"), ("ix_otp_challenges_expires_at", "expires_at")):
        if name not in indexes: op.create_index(name, "otp_challenges", [col], unique=False)

    if not _has_table("password_reset_tokens"):
        op.create_table("password_reset_tokens", sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("token_hash"))
    if "ix_password_reset_tokens_user_id" not in _indexes("password_reset_tokens"):
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"], unique=False)

    if not _has_table("recovery_codes"):
        op.create_table("recovery_codes", sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"))
    if "ix_recovery_codes_user_id" not in _indexes("recovery_codes"):
        op.create_index("ix_recovery_codes_user_id", "recovery_codes", ["user_id"], unique=False)

    if not _has_table("recovery_requests"):
        op.create_table("recovery_requests", sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("reference", sa.String(length=20), nullable=False), sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("identifier", sa.String(length=120), nullable=False), sa.Column("contact_email", sa.String(length=120), nullable=False),
            sa.Column("created_estimate", sa.String(length=60), server_default="", nullable=False),
            sa.Column("last_login_estimate", sa.String(length=60), server_default="", nullable=False),
            sa.Column("reason", sa.String(length=1000), nullable=False), sa.Column("extra", sa.String(length=1000), server_default="", nullable=False),
            sa.Column("status", sa.String(length=20), server_default="received", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("reference", name="uq_recovery_requests_reference"))


def downgrade():
    # The child checkout-details revision does not own these recovery tables.
    for table in ("recovery_requests", "recovery_codes", "password_reset_tokens", "otp_challenges"):
        if sa.inspect(op.get_bind()).has_table(table):
            op.drop_table(table)
