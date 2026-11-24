from pydantic import BaseModel, field_validator, model_validator
from typing import Any, Dict, Literal, Optional, List
from datetime import datetime
import json

from backend.schemas.project import BrandKit

# ── Target Market: structured region + city selection ───────────────────────
# Backend-owned single source of truth for region options and their curated
# city lists — the frontend must not keep its own hardcoded copy (see the
# GET /api/brands/target-market-config endpoint, which serves this).
TARGET_MARKET_REGIONS = ("local", "india", "us", "europe", "global", "other")

TARGET_MARKET_CONFIG: Dict[str, Any] = {
    "regions": [
        {"value": "local", "label": "Local / City-specific"},
        {"value": "india", "label": "India"},
        {"value": "us", "label": "United States"},
        {"value": "europe", "label": "Europe"},
        {"value": "global", "label": "Global"},
        {"value": "other", "label": "Other"},
    ],
    # Curated per-region city lists. "local"/"global"/"other" intentionally have
    # no curated list: "local" cities are free-text (the user names their own
    # city/cities), "global" clears cities entirely, and "other" is a free-text
    # custom_region.
    "cities": {
        "india": ["Delhi", "Noida", "Gurugram", "Mumbai", "Bangalore", "Pune", "Hyderabad", "Chennai", "Kolkata", "Ahmedabad"],
        "us": ["New York", "Los Angeles", "Chicago", "San Francisco", "Austin", "Seattle", "Boston", "Miami", "Dallas", "Atlanta"],
        "europe": ["London", "Paris", "Berlin", "Madrid", "Amsterdam", "Milan", "Dublin", "Stockholm", "Zurich", "Lisbon"],
    },
}


class TargetMarket(BaseModel):
    """Strict shape for a NEW target_market write. Validation:
      local  -> cities must have >= 1 entry
      global -> cities forced empty (no error if sent, just cleared)
      india/us/europe -> cities optional (0+)
      other  -> requires custom_region OR >= 1 city
    """
    region: Literal["local", "india", "us", "europe", "global", "other"]
    cities: List[str] = []
    custom_region: Optional[str] = None

    @field_validator("cities", mode="before")
    @classmethod
    def _default_cities(cls, value):
        return value or []

    @model_validator(mode="after")
    def _validate_region_rules(self):
        cities = self.cities or []
        if self.region == "local" and len(cities) < 1:
            raise ValueError("target_market region 'local' requires at least one city")
        if self.region == "global":
            self.cities = []  # forced empty, never an error
        if self.region == "other":
            has_custom = bool(self.custom_region and self.custom_region.strip())
            if not has_custom and len(cities) < 1:
                raise ValueError("target_market region 'other' requires custom_region or at least one city")
        return self


class TargetMarketOut(BaseModel):
    """Lenient OUTPUT shape — deliberately has NO Literal constraint on region,
    unlike TargetMarket above, so a legacy stored value (e.g. a bare region
    string that predates the six-option enum) can still be served without
    failing response validation. Always populated via normalize_target_market."""
    region: Optional[str] = None
    cities: List[str] = []
    custom_region: Optional[str] = None


_DEFAULT_TARGET_MARKET: Dict[str, Any] = {"region": None, "cities": [], "custom_region": None}


def normalize_target_market(value: Any) -> Dict[str, Any]:
    """
    Back-compat read/normalize boundary for target_market. Accepts whatever
    shape a BrandConfig row (or a raw request field) might hold and returns
    ONE canonical dict shape: {"region", "cities", "custom_region"}.

    Handles, in order:
      - None (never set)                         -> the default shape
      - a TargetMarket instance                   -> its dict
      - an already-structured dict                -> coerced/defaulted
      - a JSON-encoded structured string           -> parsed, then coerced
      - a legacy bare string (e.g. "India")        -> {region: "india", cities: []}

    This is intentionally lenient, NOT validation: a legacy string is
    preserved (lowercased) even when it doesn't match one of the six current
    region options, so historical data can never fail a read. The strict
    TargetMarket model above is what enforces the six-option Literal and the
    cities/custom_region rules, and only applies to NEW writes.
    """
    if value is None:
        return dict(_DEFAULT_TARGET_MARKET)

    if isinstance(value, TargetMarket):
        return value.model_dump()

    if isinstance(value, dict):
        return {
            "region": value.get("region"),
            "cities": value.get("cities") or [],
            "custom_region": value.get("custom_region"),
        }

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return dict(_DEFAULT_TARGET_MARKET)
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return {
                "region": parsed.get("region"),
                "cities": parsed.get("cities") or [],
                "custom_region": parsed.get("custom_region"),
            }
        # Legacy bare string (the original single-string Target Market value).
        return {"region": stripped.lower(), "cities": [], "custom_region": None}

    return dict(_DEFAULT_TARGET_MARKET)


# ── Social handles: multi-platform profile URLs ──────────────────────────────
SOCIAL_PLATFORMS = ("instagram", "linkedin", "x", "youtube", "facebook", "tiktok")


def extract_instagram_username(value: Optional[str]) -> str:
    """Pulls the bare Instagram username out of either a bare handle or a full
    profile URL (scheme/www optional, leading '@' or trailing '/' tolerated).
    Used to keep the legacy brand_handle column (bare username) in sync with
    social_handles["instagram"] (a full URL)."""
    if not value:
        return ""
    v = value.strip()
    if not v:
        return ""
    if "instagram.com" in v:
        v = v.split("instagram.com", 1)[1]
    v = v.strip("/").split("/")[0].split("?")[0]
    return v.lstrip("@")


def normalize_social_handles(value: Any, brand_handle: Optional[str] = None) -> Dict[str, str]:
    """
    Back-compat read/normalize boundary for social_handles, mirroring
    normalize_target_market() above. Accepts whatever shape the social_handles
    column (or a raw request field) might hold and returns ONE canonical shape:
    a dict of {platform: profile_url}, restricted to SOCIAL_PLATFORMS.

    Handles, in order:
      - an already-structured dict                 -> filtered to SOCIAL_PLATFORMS
      - a JSON-encoded dict string                  -> parsed, then filtered
      - None / unparseable, with a legacy brand_handle -> synthesized
        {"instagram": "https://instagram.com/<brand_handle>"}
      - None / unparseable, with no brand_handle    -> {}

    This is intentionally lenient, NOT validation: an unknown key is dropped
    rather than raising, so a legacy or malformed row can never fail a read.
    """
    parsed: Optional[dict] = None
    if isinstance(value, dict):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            candidate = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            candidate = None
        if isinstance(candidate, dict):
            parsed = candidate

    if parsed is not None:
        return {
            platform: url
            for platform, url in parsed.items()
            if platform in SOCIAL_PLATFORMS and url
        }

    if brand_handle:
        return {"instagram": f"https://instagram.com/{brand_handle}"}

    return {}


# ── Brand Brief: structured 6-field brand summary ────────────────────────────
# Will eventually replace the free-text brand_context in the report-generation
# prompt; not yet threaded there (see build_system_prompt).
BRAND_BRIEF_KEYS = (
    "what_we_do",
    "positioning",
    "target_audience",
    "differentiators",
    "products_services",
    "tone_of_voice",
)

_DEFAULT_BRAND_BRIEF: Dict[str, str] = {key: "" for key in BRAND_BRIEF_KEYS}


def normalize_brand_brief(value: Any) -> Dict[str, str]:
    """
    Back-compat read/normalize boundary for brand_brief, mirroring
    normalize_target_market/normalize_social_handles above. Accepts whatever
    shape the brand_brief column might hold and returns ONE canonical shape:
    all six BRAND_BRIEF_KEYS present, each a string ("" when missing, not a
    string, or the row predates this column).

    Handles, in order:
      - an already-structured dict   -> coerced to the 6 keys, extras dropped
      - a JSON-encoded dict string    -> parsed, then coerced
      - None / unparseable / anything else -> the all-empty shape

    Intentionally lenient, NOT validation — a legacy or malformed row can
    never fail a read.
    """
    parsed: Optional[dict] = None
    if isinstance(value, dict):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            candidate = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            candidate = None
        if isinstance(candidate, dict):
            parsed = candidate

    if parsed is None:
        return dict(_DEFAULT_BRAND_BRIEF)

    return {
        key: parsed[key] if isinstance(parsed.get(key), str) else ""
        for key in BRAND_BRIEF_KEYS
    }


# ── Shared base ─────────────────────────────────────────────────────────────
class BrandConfigBase(BaseModel):
    brand_name: str
    website_url: Optional[str] = None
    category: str
    brand_context: Optional[str] = None
    additional_notes: Optional[str] = None
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
    social_handles: Optional[Dict[str, str]] = None
    brand_brief: Optional[Dict[str, str]] = None
    pipeline_status: str = "pending"
    target_market: Optional[TargetMarketOut] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("target_market", mode="before")
    @classmethod
    def _normalize_target_market(cls, value):
        # Stored on the ORM row as a raw JSON string (Text column, possibly a
        # legacy bare string) — normalize_target_market() is the back-compat
        # shim that turns any of those shapes into the canonical dict here.
        return normalize_target_market(value)

    @field_validator("social_handles", mode="before")
    @classmethod
    def _normalize_social_handles(cls, value, info):
        # brand_handle is declared above this field, so it is already in
        # info.data by the time this runs — used as the legacy-row fallback.
        return normalize_social_handles(value, info.data.get("brand_handle"))

    @field_validator("brand_brief", mode="before")
    @classmethod
    def _normalize_brand_brief(cls, value):
        return normalize_brand_brief(value)


# ── Search competitors request ───────────────────────────────────────────────
class CompetitorInput(BaseModel):
    name: str
    url: Optional[str] = None


class BrandSearchRequest(BaseModel):
    brand_name: str
    website_url: str
    category: str
    user_competitors: Optional[List[CompetitorInput]] = []
    industry: Optional[str] = None  # unused by the frontend as of the Target Market/Research-Brand change; category now carries this signal. Kept for backward compatibility.
    region: Optional[str] = None  # legacy UI label: "Target Market" — a plain string. Kept for the unchanged frontend.
    target_market: Optional[TargetMarket] = None  # structured Target Market, not yet sent by the frontend; when
    # present it takes priority over `region` for discovery's geography scoping (see tavily_comp.search_candidates).
    reference_ref_ids: Optional[List[str]] = None


# ── Research brand context (auto-fill) ───────────────────────────────────────
class BrandContextResearchRequest(BaseModel):
    brand_name: str
    website_url: str
    category: str


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
    additional_notes: Optional[str] = None
    selected_competitors: List[CompetitorConfirmed]
    brand_handle: Optional[str] = None
    social_handles: Dict[str, str]  # REQUIRED — {platform: profile_url}, platform in SOCIAL_PLATFORMS.
    # At least one non-empty entry (see _validate_social_handles below); the frontend now always
    # sends a user-verified value here instead of forwarding brand_handle silently.
    brand_kit: Optional[BrandKit] = None
    reference_docs: Optional[List[dict]] = None
    target_market: TargetMarket
    brand_brief: Dict[str, str]  # REQUIRED — {field: value}, field in BRAND_BRIEF_KEYS. At least one
    # non-empty entry (see _validate_brand_brief below); the UI now always sends a user-verified brief.

    @field_validator("social_handles")
    @classmethod
    def _validate_social_handles(cls, value):
        if not value or not any((v or "").strip() for v in value.values()):
            raise ValueError("social_handles is required — add at least one platform's profile URL")
        return value

    @field_validator("brand_brief")
    @classmethod
    def _validate_brand_brief(cls, value):
        if not value or not any((v or "").strip() for v in value.values()):
            raise ValueError("brand_brief is required — fill in at least one field")
        return value


# ── Generate Brand Brief (onboarding-time, pre-confirm) ──────────────────────
class BrandBriefRequest(BaseModel):
    brand_name: str
    website_url: str
    category: str
    target_market: Optional[TargetMarket] = None
    additional_notes: Optional[str] = None
    reference_docs: Optional[List[dict]] = None  # [{ref_id, filename, ...}] — text is loaded server-side by ref_id.


# ── Status polling ────────────────────────────────────────────────────────────
class BrandStatusResponse(BaseModel):
    id: str
    pipeline_status: str   # pending | running | complete | failed
    social_scraped: bool


# ── Project details drawer edits (post-onboarding field updates) ────────────
class BrandBriefUpdate(BaseModel):
    what_we_do: str = ""
    positioning: str = ""
    target_audience: str = ""
    differentiators: str = ""
    products_services: str = ""
    tone_of_voice: str = ""


class SocialHandlesUpdate(BaseModel):
    instagram: str = ""
    linkedin: str = ""
    x: str = ""
    youtube: str = ""
    facebook: str = ""
    tiktok: str = ""


class BrandContextUpdate(BaseModel):
    website_url: str
    category: str
    target_market: str
