"""Add per-user session invalidation without changing existing accounts."""

from alembic import op
import sqlalchemy as sa

revision = "d82f6a9b3104"
down_revision = "c61d8e4a2b90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("users", "session_version")
