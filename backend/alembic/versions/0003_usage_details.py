"""add provider request id, tokens and audio length to usage records

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provider_requests", sa.Column("provider_request_id", sa.String(length=255), nullable=True))
    op.add_column("provider_requests", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("provider_requests", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("provider_requests", sa.Column("audio_seconds", sa.Float(), nullable=True))
    op.create_index(
        op.f("ix_provider_requests_provider_request_id"), "provider_requests", ["provider_request_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provider_requests_provider_request_id"), table_name="provider_requests")
    op.drop_column("provider_requests", "audio_seconds")
    op.drop_column("provider_requests", "output_tokens")
    op.drop_column("provider_requests", "input_tokens")
    op.drop_column("provider_requests", "provider_request_id")
