"""add report_sections

Revision ID: 01345c035d4f
Revises: 409b78973a44
Create Date: 2026-11-13

NOTE: Alembic is not wired up in this project (see d567dcef6bc6_add_reports.py
for the full explanation — empty env.py, placeholder alembic.ini URL). The
"report_sections" table was created directly via Base.metadata.create_all()
scoped to ReportSection.__table__, matching how "reports" and "report_shares"
were created. This revision exists only as a correct record.
"""
from alembic import op
import sqlalchemy as sa

revision = "01345c035d4f"
down_revision = "409b78973a44"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_sections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.String(length=36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("section_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_report_sections_report_id", "report_sections", ["report_id"])
    op.create_index("ix_report_sections_report_id_order", "report_sections", ["report_id", "order"])


def downgrade():
    op.drop_index("ix_report_sections_report_id_order", table_name="report_sections")
    op.drop_index("ix_report_sections_report_id", table_name="report_sections")
    op.drop_table("report_sections")
