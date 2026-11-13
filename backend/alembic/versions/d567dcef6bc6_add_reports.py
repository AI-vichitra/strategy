"""add reports

Revision ID: d567dcef6bc6
Revises: b3ec31ba252a
Create Date: 2026-11-12

NOTE: Alembic is not actually wired up in this project (env.py and every
prior revision file under versions/ are empty stubs, and alembic.ini has a
placeholder sqlalchemy.url) — `alembic upgrade head` will not run this.
The "reports" table was created directly via Base.metadata.create_all()
scoped to Report.__table__ (matching how the existing tables were created).
This revision exists only as a correct record in case Alembic is wired up
properly in the future.
"""
from alembic import op
import sqlalchemy as sa

revision = "d567dcef6bc6"
down_revision = "b3ec31ba252a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", sa.String(length=36), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("agent_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("chart_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("reports")
