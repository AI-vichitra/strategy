"""
Share Service
==============
Public, unguessable read-only links for Report rows. A share token resolves
to a minimal, user-free view of a report's content — no auth required to
read it, but creating/revoking a share always requires owning the report.
"""

import secrets
import logging
from typing import Optional

from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.report import Report
from backend.models.report_share import ReportShare
from backend.models.project import Project
from backend.models.brand import BrandConfig

logger = logging.getLogger(__name__)


async def _get_owned_report(db: AsyncSession, report_id: str, user_id: str) -> Optional[Report]:
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_share(db: AsyncSession, report_id: str, user_id: str) -> Optional[str]:
    """Returns a share token, or None if the report doesn't exist / isn't the user's."""
    report = await _get_owned_report(db, report_id, user_id)
    if not report:
        return None

    existing_result = await db.execute(
        select(ReportShare).where(ReportShare.report_id == report_id, ReportShare.revoked == False)  # noqa: E712
    )
    existing = existing_result.scalars().first()
    if existing:
        return existing.token

    token = secrets.token_urlsafe(32)
    share = ReportShare(report_id=report_id, token=token, revoked=False)
    db.add(share)
    await db.commit()
    return token


async def revoke_share(db: AsyncSession, report_id: str, user_id: str) -> bool:
    """Revokes all active shares for a report owned by user_id. Returns True if the report is theirs."""
    report = await _get_owned_report(db, report_id, user_id)
    if not report:
        return False

    await db.execute(
        update(ReportShare)
        .where(ReportShare.report_id == report_id)
        .values(revoked=True)
    )
    await db.commit()
    return True


async def get_shared_report(db: AsyncSession, token: str) -> Optional[dict]:
    """Resolves a token to a public, read-only view. Never includes internal ids."""
    share_result = await db.execute(
        select(ReportShare).where(ReportShare.token == token, ReportShare.revoked == False)  # noqa: E712
    )
    share = share_result.scalar_one_or_none()
    if not share:
        return None

    report_result = await db.execute(select(Report).where(Report.id == share.report_id))
    report = report_result.scalar_one_or_none()
    if not report:
        return None

    brand_result = await db.execute(
        select(BrandConfig.brand_name)
        .join(Project, Project.brand_config_id == BrandConfig.id)
        .where(Project.id == report.project_id)
    )
    brand_row = brand_result.first()
    brand_name = brand_row[0] if brand_row else None

    return {
        "title": report.title,
        "content": report.content,
        "agent_type": report.agent_type,
        "brand_name": brand_name,
        "created_at": report.created_at,
    }
