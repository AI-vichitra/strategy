"""
Report Service
===============
Server-side versioned snapshots of qualifying assistant outputs. Additive and
independent of the Message/chat/streaming path — a Report row is an immutable
copy of a Message's content taken at generation time, so it survives later
edits or deletions of the underlying chat history.
"""

import re
import logging
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.report import Report
from backend.models.project import Project

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+)$", re.MULTILINE)
_LEADING_MD_RE = re.compile(r"^[#*`\s]+")
_TRAILING_MD_RE = re.compile(r"[#*`\s]+$")


def _clean_heading_text(text: str) -> str:
    """Strips markdown emphasis/heading/code markers (**, *, `, #) from a captured heading."""
    text = _LEADING_MD_RE.sub("", text)
    text = _TRAILING_MD_RE.sub("", text)
    return text.strip()


def _derive_title(content: str, fallback: str) -> str:
    match = _HEADING_RE.search(content or "")
    if match:
        title = _clean_heading_text(match.group(1))
        if title:
            return title
    return fallback


async def create_report_snapshot(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    agent_type: str,
    content: str,
    message_id: Optional[str] = None,
) -> Report:
    from backend.services import output_validator

    version_result = await db.execute(
        select(func.max(Report.version)).where(Report.project_id == project_id)
    )
    next_version = (version_result.scalar() or 0) + 1

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    fallback_title = (project.title if project and project.title else agent_type) or "Untitled Report"
    title = _derive_title(content, fallback_title)

    validation = output_validator.validate_output(content, agent_type)
    chart_count = validation.get("chart_count", 0)

    report = Report(
        project_id=project_id,
        user_id=user_id,
        message_id=message_id,
        agent_type=agent_type,
        title=title,
        content=content,
        version=next_version,
        chart_count=chart_count,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    from backend.services import section_service
    try:
        await section_service.parse_report_into_sections(db, report.id, report.content)
    except Exception as e:
        logger.warning(f"[report_service] Auto-parse into sections failed for report {report.id}: {e}")

    return report


async def list_reports(db: AsyncSession, project_id: str, user_id: str):
    """Returns version metadata only — content is never selected or loaded."""
    result = await db.execute(
        select(
            Report.id,
            Report.message_id,
            Report.version,
            Report.title,
            Report.agent_type,
            Report.chart_count,
            Report.created_at,
        )
        .where(Report.project_id == project_id, Report.user_id == user_id)
        .order_by(Report.version.desc())
    )
    return result.all()


async def get_report(db: AsyncSession, report_id: str, user_id: str) -> Optional[Report]:
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    return result.scalar_one_or_none()
