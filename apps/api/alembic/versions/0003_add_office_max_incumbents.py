"""Add max_incumbents column to office"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = '0003_add_office_max_incumbents'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch operations for SQLite compatibility
    with op.batch_alter_table('office') as batch_op:
        batch_op.add_column(sa.Column('max_incumbents', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('office') as batch_op:
        batch_op.drop_column('max_incumbents')
