from fastapi import APIRouter, HTTPException

from backend.services import registry_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── GET /api/agents — full catalog (categories + enabled agents) ────────────
@router.get("")
async def list_agents():
    return {
        "categories": registry_service.get_categories(),
        "agents": registry_service.get_agents(enabled_only=True),
    }


# ── GET /api/agents/{agent_id} — single agent lookup by id ──────────────────
@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    for agent in registry_service.get_agents(enabled_only=False):
        if agent.get("id") == agent_id:
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")
