from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Shared base ─────────────────────────────────────────────────────────────
class BrandConfigBase(BaseModel):
    brand_name: str
    website_url: Optional[str] = None
    category: str
    brand_context: Optional[str] = None
    competitors: Optional[str] = None
    social_metrics: Optional[str] = None


# ── DB create / response ─────────────────────────────────────────────────────
class BrandConfigCreate(BrandConfigBase):
    pass


class BrandConfigResponse(BrandConfigBase):
    id: str
    user_id: str
    brand_slug: Optional[str] = None
    brand_handle: Optional[str] = None
    pipeline_status: str = "pending"
    created_at: datetime

    class Config:
        from_attributes = True


# ── Search competitors request ───────────────────────────────────────────────
class CompetitorInput(BaseModel):
    name: str
    url: Optional[str] = None


class BrandSearchRequest(BaseModel):
    brand_name: str
    website_url: str
    category: str
    user_competitors: Optional[List[CompetitorInput]] = []


# ── Confirm brand + kick off pipeline ────────────────────────────────────────
class CompetitorConfirmed(BaseModel):
    name: str
    website_url: Optional[str] = None
    handle: Optional[str] = None


class BrandConfirmRequest(BaseModel):
    brand_name: str
    website_url: str
    category: str
    brand_context: Optional[str] = None
    selected_competitors: List[CompetitorConfirmed]
    brand_handle: Optional[str] = None


# ── Status polling ────────────────────────────────────────────────────────────
class BrandStatusResponse(BaseModel):
    id: str
    pipeline_status: str   # pending | running | complete | failed
    social_scraped: bool
