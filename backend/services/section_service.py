"""
Section Service
================
Splits a Report's markdown content into editable ReportSection rows (one per
H3 block, plus a leading section for anything before the first H3), and
provides CRUD + reordering + reassembly on top of them.
"""

import re
import logging
from typing import List, Optional

from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.report_section import ReportSection

logger = logging.getLogger(__name__)

_H3_SPLIT_RE = re.compile(r"(?=^###[ \t]+.+$)", re.MULTILINE)
_H3_TITLE_RE = re.compile(r"^###[ \t]+(.+)$", re.MULTILINE)
_RECHARTS_FENCE_RE = re.compile(r"```recharts\b", re.IGNORECASE)
_MD_TABLE_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", re.MULTILINE)


def _clean_title(text: str) -> str:
    return text.strip().strip("*").strip()


def _classify(block: str) -> str:
    if _RECHARTS_FENCE_RE.search(block):
        return "chart"
    if _MD_TABLE_RE.search(block):
        return "table"
    return "heading"


async def parse_report_into_sections(db: AsyncSession, report_id: str, content: str) -> List[ReportSection]:
    """
    Splits `content` on H3 headings. Everything before the first H3 becomes
    section 0 (type="text"). No-op (returns existing sections) if the report
    already has sections.
    """
    existing = await get_sections(db, report_id)
    if existing:
        return existing

    content = content or ""
    blocks = _H3_SPLIT_RE.split(content)

    sections: List[ReportSection] = []
    order = 0
    for block in blocks:
        if not block.strip():
            continue
        is_h3 = block.lstrip().startswith("###")
        if not is_h3:
            sections.append(ReportSection(
                report_id=report_id,
                order=order,
                section_type="text",
                title=None,
                content=block.strip(),
                visible=True,
            ))
        else:
            title_match = _H3_TITLE_RE.match(block.lstrip())
            title = _clean_title(title_match.group(1)) if title_match else None
            sections.append(ReportSection(
                report_id=report_id,
                order=order,
                section_type=_classify(block),
                title=title,
                content=block.strip(),
                visible=True,
            ))
        order += 1

    db.add_all(sections)
    await db.commit()
    for s in sections:
        await db.refresh(s)
    return sections


async def get_section(db: AsyncSession, section_id: int) -> Optional[ReportSection]:
    result = await db.execute(select(ReportSection).where(ReportSection.id == section_id))
    return result.scalar_one_or_none()


async def get_sections(db: AsyncSession, report_id: str) -> List[ReportSection]:
    result = await db.execute(
        select(ReportSection)
        .where(ReportSection.report_id == report_id)
        .order_by(ReportSection.order)
    )
    return list(result.scalars().all())


async def create_section(
    db: AsyncSession,
    report_id: str,
    after_order: int,
    title: Optional[str],
    content: str,
    section_type: str,
) -> ReportSection:
    """Shifts every section with order > after_order up by 1, then inserts at after_order + 1."""
    await db.execute(
        update(ReportSection)
        .where(ReportSection.report_id == report_id, ReportSection.order > after_order)
        .values(order=ReportSection.order + 1)
    )

    section = ReportSection(
        report_id=report_id,
        order=after_order + 1,
        section_type=section_type,
        title=title,
        content=content,
        visible=True,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


async def update_section(
    db: AsyncSession,
    section_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    visible: Optional[bool] = None,
) -> Optional[ReportSection]:
    result = await db.execute(select(ReportSection).where(ReportSection.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        return None

    if title is not None:
        section.title = title
    if content is not None:
        section.content = content
    if visible is not None:
        section.visible = visible

    await db.commit()
    await db.refresh(section)
    return section


async def delete_section(db: AsyncSession, section_id: int) -> bool:
    result = await db.execute(select(ReportSection).where(ReportSection.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        return False

    report_id = section.report_id
    await db.delete(section)
    await db.commit()

    remaining = await get_sections(db, report_id)
    for idx, s in enumerate(remaining):
        if s.order != idx:
            s.order = idx
    await db.commit()
    return True


async def reorder_sections(db: AsyncSession, report_id: str, section_ids: List[int]) -> List[ReportSection]:
    """Sets `order` from each id's position in `section_ids`."""
    for idx, section_id in enumerate(section_ids):
        await db.execute(
            update(ReportSection)
            .where(ReportSection.id == section_id, ReportSection.report_id == report_id)
            .values(order=idx)
        )
    await db.commit()
    return await get_sections(db, report_id)


async def get_finalized_content(db: AsyncSession, report_id: str) -> str:
    """Reassembles visible sections, in order, back into one markdown string."""
    sections = await get_sections(db, report_id)
    return "\n\n".join(s.content for s in sections if s.visible)
