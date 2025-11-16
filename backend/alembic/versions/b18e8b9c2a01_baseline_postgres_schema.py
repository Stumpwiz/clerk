"""Baseline schema for PostgreSQL

Revision ID: b18e8b9c2a01
Revises: None
Create Date: 2025-11-15

This migration creates the initial schema using PostgreSQL-compatible operations.
It avoids SQLite-specific batch_alter_table and establishes:
  - Tables: body, office, person, term, letters
  - View: report_record (read-only reporting view)
  - Proper foreign key constraints between tables
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b18e8b9c2a01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Table: body
    op.create_table(
        "body",
        sa.Column("body_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=45), nullable=False),
        sa.Column("mission", sa.String(length=512), nullable=True),
        sa.Column(
            "body_precedence",
            sa.Float(),
            nullable=False,
            comment="Used for ordering in reports and on web pages",
        ),
    )

    # Table: office
    op.create_table(
        "office",
        sa.Column("office_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=45), nullable=True),
        sa.Column("office_precedence", sa.Float(), nullable=True),
        sa.Column("office_body_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["office_body_id"], ["body.body_id"], name="fk_office_body"),
    )

    # Table: person
    op.create_table(
        "person",
        sa.Column("personid", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("first", sa.String(length=15), nullable=True),
        sa.Column("last", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=45), nullable=True),
        sa.Column("phone", sa.String(length=19), nullable=True),
        sa.Column("apt", sa.String(length=4), nullable=True),
        sa.UniqueConstraint("first", "last", name="uix_person_first_last"),
    )

    # Table: term (composite PK, FKs to person and office)
    op.create_table(
        "term",
        sa.Column("termpersonid", sa.Integer(), nullable=False),
        sa.Column("termofficeid", sa.Integer(), nullable=False),
        sa.Column("start", sa.Date(), nullable=True),
        sa.Column("end", sa.Date(), nullable=True),
        sa.Column("ordinal", sa.String(length=7), nullable=True),
        sa.PrimaryKeyConstraint("termpersonid", "termofficeid", name="pk_term"),
        sa.ForeignKeyConstraint(["termpersonid"], ["person.personid"], name="fk_term_person"),
        sa.ForeignKeyConstraint(["termofficeid"], ["office.office_id"], name="fk_term_office"),
    )

    # Table: letters
    op.create_table(
        "letters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("header", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
    )

    # View: report_record — a reporting view joining person, term, office, body
    # Note: quote the "end" column because it is a reserved keyword.
    op.execute(
        sa.text(
            """
            CREATE VIEW report_record AS
            SELECT
                p.personid AS person_id,
                p.first,
                p.last,
                p.email,
                p.phone,
                p.apt,
                t.start,
                t."end",
                t.ordinal,
                t.termpersonid AS term_person_id,
                t.termofficeid AS term_office_id,
                o.office_id AS office_id,
                o.title,
                o.office_precedence,
                o.office_body_id,
                b.body_id,
                b.name,
                b.body_precedence
            FROM term t
            JOIN person p ON p.personid = t.termpersonid
            JOIN office o ON o.office_id = t.termofficeid
            JOIN body b ON b.body_id = o.office_body_id
            """
        )
    )


def downgrade() -> None:
    # Drop view first due to dependencies
    op.execute(sa.text("DROP VIEW IF EXISTS report_record"))

    # Drop tables in reverse order of creation
    op.drop_table("letters")
    op.drop_table("term")
    op.drop_table("person")
    op.drop_table("office")
    op.drop_table("body")
