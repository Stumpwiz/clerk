"""Add the minimal administrator flag without promoting existing accounts."""

from alembic import op
import sqlalchemy as sa

revision = "c61d8e4a2b90"
down_revision = "92d6f8a1c430"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("users", "is_admin")
