"""
PPTX Templates router
======================
Public catalog of selectable PPTX visual templates — mirrors routers/agents.py
(same mounting convention: the router carries its own prefix, no auth) so the
frontend's export-time template picker has something to list from.

Only a trimmed public DTO is ever returned — never the full TemplateSpec
(fonts/type_scale/palette/backgrounds/geometry/fit/slots/art), which stays an
internal rendering detail of pptx_service/template_service.
"""

from typing import Any, Dict

from fastapi import APIRouter

from backend.services import template_service

router = APIRouter(prefix="/api/pptx-templates", tags=["pptx-templates"])


def _to_public_dto(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Trims a raw template registry entry down to what a template picker
    needs — id/name/description/preview only."""
    return {
        "id": entry.get("id"),
        "name": entry.get("name"),
        "description": entry.get("description"),
        "preview": entry.get("preview"),
    }


# ── GET /api/pptx-templates — public catalog of enabled PPTX templates ─────
@router.get("")
async def list_pptx_templates():
    return [_to_public_dto(t) for t in template_service.get_templates(enabled_only=True)]
