"""Recreate users table for access control

Revision ID: 0002
Revises: 0001
Create Date: 2025-10-12 12:05:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old users table completely (has obsolete password_hash column)
    try:
        op.drop_table('users')
    except Exception:
        # If old users table doesn't exist, ignore
        pass

    # Recreate with new schema (no password_hash, clean structure)
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=45), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uix_user_email')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Insert initial admin user
    op.execute("""
        INSERT INTO users (username, email, role)
        VALUES ('George Wright', 'geo@loyola.edu', 'admin')
    """)


def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    # Note: Cannot restore old users table structure in downgrade
    # This would require manual intervention to restore from backup
