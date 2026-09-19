"""Persist generated letter PDFs in PostgreSQL.

Revision ID: 92d6f8a1c430
Revises: 7a4d1f8c2e91
"""
from alembic import op
import sqlalchemy as sa

revision = "92d6f8a1c430"
down_revision = "7a4d1f8c2e91"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "generated_letters",
        sa.Column("filename", sa.Text(), primary_key=True),
        sa.Column("pdf_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("generated_letters")
