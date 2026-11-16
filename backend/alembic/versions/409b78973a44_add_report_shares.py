"""add report_shares

Revision ID: 409b78973a44
Revises: d567dcef6bc6
Create Date: 2026-11-12

NOTE: Alembic is not wired up in this project (see d567dcef6bc6_add_reports.py
for the full explanation — empty env.py, empty prior revisions, placeholder
alembic.ini URL). The "report_shares" table was created directly via
Base.metadata.create_all() scoped to ReportShare.__table__, matching how
"reports" was created. This revision exists only as a correct record.
"""
from alembic import op
import sqlalchemy as sa

revision = "409b78973a44"
down_revision = "d567dcef6bc6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_shares",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_report_shares_token", "report_shares", ["token"], unique=True)


def downgrade():
    op.drop_index("ix_report_shares_token", table_name="report_shares")
    op.drop_table("report_shares")
