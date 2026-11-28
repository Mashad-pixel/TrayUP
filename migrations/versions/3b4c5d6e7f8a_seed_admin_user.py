"""seed_admin_user

Revision ID: 3b4c5d6e7f8a
Revises: 2a3b4c5d6e7f
Create Date: 2026-11-26 16:16:00.000000

This revision used to insert demo administrator and kitchen accounts with published passwords,
and it ran on every production deployment. It now does nothing, so no account is created with a
known password. Create real staff with the CLI instead:

    flask --app wsgi:app setup-admin --email you@example.com --name "Your Name"

Accounts that were created by the old version are deactivated by the migration that follows
(a9f8e7d6c5b4), but only while they still use the published password.
"""

revision = '3b4c5d6e7f8a'
down_revision = '2a3b4c5d6e7f'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
