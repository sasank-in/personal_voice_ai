"""repair invalid stored languages and only allow supported codes

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# Fixed here rather than imported, so this migration never changes when the app's list does.
LANGUAGES = ("as-IN", "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN")
ALLOWED = ", ".join(f"'{code}'" for code in LANGUAGES)


def repair(table: str) -> None:
    # A bare code such as 'en' becomes its regional form; anything else becomes English.
    op.execute(
        f"""
        UPDATE {table} SET language = CASE
            WHEN lower(split_part(language, '-', 1)) || '-IN' IN ({ALLOWED})
                THEN lower(split_part(language, '-', 1)) || '-IN'
            ELSE 'en-IN'
        END
        WHERE language NOT IN ({ALLOWED})
        """
    )


def upgrade() -> None:
    for table in ("users", "voice_profiles"):
        repair(table)
        op.create_check_constraint(f"ck_{table}_language", table, f"language IN ({ALLOWED})")


def downgrade() -> None:
    for table in ("users", "voice_profiles"):
        op.drop_constraint(f"ck_{table}_language", table, type_="check")
