from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import uuid
from datetime import datetime

class BrandConfig(Base):
    __tablename__ = "brand_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    brand_name = Column(String, nullable=False)
    website_url = Column(String, nullable=True)
    category = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)
    brand_context = Column(Text, nullable=True)
    competitors = Column(Text, nullable=True)          # JSON list of {name, url}
    social_metrics = Column(Text, nullable=True)       # Kept for backwards compat / status signals
    # New pipeline tracking columns
    brand_slug = Column(String, nullable=True)         # Docs folder name: brand_name_id[:8]
    brand_handle = Column(String, nullable=True)       # Discovered Instagram handle (bare username; kept in
                                                          # sync with social_handles["instagram"] — see
                                                          # schemas.brand.normalize_social_handles)
    social_handles = Column(Text, nullable=True)        # JSON: {platform: profile_url}, platform in
                                                          # schemas.brand.SOCIAL_PLATFORMS. Always read via
                                                          # schemas.brand.normalize_social_handles.
    confirmed_competitor_handles = Column(Text, nullable=True)  # JSON list of handles
    reference_docs = Column(Text, nullable=True)        # JSON list of {ref_id, filename, text}
    pipeline_status = Column(String, default="pending", nullable=False)  # pending | running | complete | failed
    kb_json = Column(Text, nullable=True)               # Compiled KB (mirrors KNOWLEDGE_BASE/{slug}_KB.json); DB is source of truth, file is local cache
    target_market = Column(Text, nullable=True)         # JSON: {region, cities, custom_region}. May also hold a
                                                          # legacy plain string (old Target Market value) on rows
                                                          # written before this column existed being migrated in
                                                          # place — always read via schemas.brand.normalize_target_market.
    additional_notes = Column(Text, nullable=True)       # Optional free-text guardrails/intent from onboarding
                                                          # (e.g. "Moving to premium positioning", "BFSI — follow
                                                          # SEBI rules"). Injected into the LLM system prompt at
                                                          # report-generation time; never used to scope research.
    brand_brief = Column(Text, nullable=True)            # JSON: the 6-key structured Brand Brief
                                                          # (schemas.brand.BRAND_BRIEF_KEYS). Not yet threaded into
                                                          # build_system_prompt — always read via
                                                          # schemas.brand.normalize_brand_brief.
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="brands")
    projects = relationship("Project", back_populates="brand", cascade="all, delete-orphan")
