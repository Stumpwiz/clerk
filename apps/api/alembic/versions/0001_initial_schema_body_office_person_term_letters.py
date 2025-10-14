"""Initial schema - body, office, person, term, letters

Revision ID: 0001
Revises: 
Create Date: 2025-10-11 12:30:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create table: body
    op.create_table(
        'body',
        sa.Column('body_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=45), nullable=False),
        sa.Column('mission', sa.String(length=512), nullable=True),
        sa.Column('body_precedence', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('body_id')
    )

    # Create table: letters
    op.create_table(
        'letters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('header', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create table: office (FK to body)
    op.create_table(
        'office',
        sa.Column('office_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=45), nullable=True),
        sa.Column('office_precedence', sa.Float(), nullable=True),
        sa.Column('office_body_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['office_body_id'], ['body.body_id']),
        sa.PrimaryKeyConstraint('office_id')
    )

    # Create table: person with unique(first,last)
    op.create_table(
        'person',
        sa.Column('personid', sa.Integer(), nullable=False),
        sa.Column('first', sa.String(length=15), nullable=True),
        sa.Column('last', sa.String(length=30), nullable=True),
        sa.Column('email', sa.String(length=45), nullable=True),
        sa.Column('phone', sa.String(length=19), nullable=True),
        sa.Column('apt', sa.String(length=4), nullable=True),
        sa.PrimaryKeyConstraint('personid'),
        sa.UniqueConstraint('first', 'last', name='uix_person_first_last')
    )

    # Create table: term (junction)
    op.create_table(
        'term',
        sa.Column('termpersonid', sa.Integer(), nullable=False),
        sa.Column('termofficeid', sa.Integer(), nullable=False),
        sa.Column('start', sa.Date(), nullable=True),
        sa.Column('end', sa.Date(), nullable=True),
        sa.Column('ordinal', sa.String(length=7), nullable=True),
        sa.ForeignKeyConstraint(['termofficeid'], ['office.office_id']),
        sa.ForeignKeyConstraint(['termpersonid'], ['person.personid']),
        sa.PrimaryKeyConstraint('termpersonid', 'termofficeid')
    )


def downgrade() -> None:
    # Drop in reverse order of dependencies
    op.drop_table('term')
    op.drop_table('person')
    op.drop_table('office')
    op.drop_table('letters')
    op.drop_table('body')
