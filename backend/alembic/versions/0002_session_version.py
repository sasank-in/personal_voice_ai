"""add session version and normalize emails

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False))
    op.execute("UPDATE users SET email = lower(trim(email))")


def downgrade() -> None:
    op.drop_column("users", "session_version")
