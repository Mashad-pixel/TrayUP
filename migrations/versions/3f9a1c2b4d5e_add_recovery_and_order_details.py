"""add account recovery request and password recovery challenge tables

Revision ID: 3f9a1c2b4d5e
Revises: 1a2b3c4d5e6f
Create Date: 2026-11-25

"""
from alembic import op
import sqlalchemy as sa


revision = "8a9b0c1d2e3f"
down_revision = "3f9a1c2b4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_recovery_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_token_hash", sa.String(length=64), nullable=True),
        sa.Column("reset_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_password_recovery_attempts_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reset_token_hash"),
    )
    op.create_index(
        "ix_password_recovery_challenges_user_id",
        "password_recovery_challenges",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "account_recovery_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ref", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("identifier", sa.String(length=120), nullable=False),
        sa.Column("contact_email", sa.String(length=120), nullable=False),
        sa.Column("created_estimate", sa.String(length=60), nullable=False),
        sa.Column("last_login_estimate", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("extra", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ref", name="uq_account_recovery_requests_ref"),
    )
    op.create_index("ix_account_recovery_requests_user_id", "account_recovery_requests", ["user_id"], unique=False)
    op.create_index(
        "ix_password_recovery_challenges_expires_at",
        "password_recovery_challenges",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_password_recovery_challenges_reset_token_hash",
        "password_recovery_challenges",
        ["reset_token_hash"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_account_recovery_requests_user_id", table_name="account_recovery_requests")
    op.drop_table("account_recovery_requests")
    op.drop_index("ix_password_recovery_challenges_reset_token_hash", table_name="password_recovery_challenges")
    op.drop_index("ix_password_recovery_challenges_expires_at", table_name="password_recovery_challenges")

    op.drop_index("ix_password_recovery_challenges_user_id", table_name="password_recovery_challenges")
    op.drop_table("password_recovery_challenges")
