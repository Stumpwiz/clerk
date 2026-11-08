"""Store normalized avatars alongside their owning user."""
from alembic import op
import sqlalchemy as sa

revision = "e93a7b2c4105"
down_revision = "d82f6a9b3104"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_bytes", sa.LargeBinary(), nullable=True))


def downgrade():
    op.drop_column("users", "avatar_bytes")
