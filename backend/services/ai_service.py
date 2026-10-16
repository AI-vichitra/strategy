"""
AI Service — Hybrid RAG-powered chat with Anthropic Claude
===========================================================

Architecture:
  - Knowledge base format: JSON files (one per source document)
    Each JSON file has: { title, url, source_type, brand, content }
  - Chunking: 500-word chunks, 100-word overlap
  - Embeddings: sentence-transformers all-MiniLM-L6-v2 (384-dim, free, local)
  - Retrieval: Hybrid — cosine similarity (dense) + BM25 keyword (sparse), RRF fusion
  - Top-K retrieved: 6 chunks
  - Index caching: in-memory per brand_slug, rebuilt only when docs folder changes
  - LLM: Anthropic Claude (streaming SSE)
"""

import os
import re
import json
import time
import logging
import asyncio
import hashlib
from typing import List, AsyncGenerator, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

# ─────────────────────────────────────────────────────────────────────────────
# Constants (your choices)
# ─────────────────────────────────────────────────────────────────────────────
CHUNK_SIZE = 500          # words per chunk
CHUNK_OVERLAP = 100       # words of overlap between adjacent chunks
TOP_K = 6                 # chunks retrieved per query
EMBED_MODEL = "all-MiniLM-L6-v2"   # 384-dim, free, local
MISTRAL_MODEL = "open-mistral-7b"

# ─────────────────────────────────────────────────────────────────────────────
# In-memory cache: brand_slug → { chunks, embeddings, bm25, mtime_hash }
# ─────────────────────────────────────────────────────────────────────────────
_index_cache: Dict[str, Dict[str, Any]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Lazy-loaded singletons
# ─────────────────────────────────────────────────────────────────────────────
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBED_MODEL)
        logger.info(f"[RAG] Loaded embedder: {EMBED_MODEL} (384-dim)")
    return _embedder


def _get_llm_provider(requested: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns tuple of (provider, api_key).
    If requested is specified, attempts that provider first if key exists.
    Supported: mistral, qwen, openai, anthropic
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key.startswith("sk-ant-"):
        openai_key = ""

    keys = {
        "mistral": os.environ.get("MISTRAL_API_KEY", "").strip(),
        "qwen": os.environ.get("QWEN_API_KEY", "").strip(),
        "openai": openai_key,
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", "").strip(),
    }

    req_clean = (requested or "").lower().strip()
    if req_clean in keys and keys[req_clean]:
        return (req_clean, keys[req_clean])

    # Default priority fallback order (mistral verified working)
    for prov in ["mistral", "qwen", "openai", "anthropic"]:
        if keys[prov]:
            return (prov, keys[prov])

    raise RuntimeError("No valid LLM API key set in environment (MISTRAL_API_KEY, QWEN_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)")




# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Load JSON knowledge base from docs folder
# ─────────────────────────────────────────────────────────────────────────────
def _get_docs_paths(brand_slug: str) -> List[str]:
    """Return the path to the centralized Knowledge Base file for a brand."""
    kb_path = os.path.join(PROJECT_ROOT, "KNOWLEDGE_BASE", f"{brand_slug}_KB.json")
    if os.path.exists(kb_path):
        return [kb_path]
    return []


def _folder_mtime_hash(brand_slug: str) -> str:
    """Returns a hash of all JSON filenames + mtimes — changes when docs are added/updated."""
    paths = _get_docs_paths(brand_slug)
    fingerprint = "|".join(f"{p}:{os.path.getmtime(p)}" for p in paths if os.path.exists(p))
    return hashlib.md5(fingerprint.encode()).hexdigest()


def _load_json_docs(brand_slug: str) -> List[Dict[str, Any]]:
    """Loads and flattens the centralized KB JSON into standardized RAG documents."""
    docs = []
    for path in _get_docs_paths(brand_slug):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            def process_entity(entity):
                name = entity.get("NAME", "Unknown")
                url = entity.get("URL", "")
                
                web_scrapped = entity.get("WEB_SCRAPPED", "")
                if web_scrapped and web_scrapped not in ("Data not found", "Deep dive JSON not found"):
                    docs.append({
                        "title": f"{name} — Deep Intelligence Report",
                        "url": url,
                        "source_type": "deep_dive",
                        "brand": name,
                        "content": web_scrapped
                    })
                    
                insta_scrapped = entity.get("INSTA_SCRAPPED", "")
                if insta_scrapped and insta_scrapped not in ("Data not found", "Instagram JSON not found"):
                    docs.append({
                        "title": f"{name} — Instagram Social Analysis",
                        "url": f"https://instagram.com/{name.lower()}",
                        "source_type": "social_instagram",
                        "brand": name,
                        "content": insta_scrapped
                    })
                    
            if isinstance(data, dict):
                if "brand" in data:
                    process_entity(data["brand"])
                if "competitors" in data and isinstance(data["competitors"], list):
                    for comp in data["competitors"]:
                        process_entity(comp)
                        
        except Exception as e:
            logger.warning(f"[RAG] Failed to load {path}: {e}")
            
    logger.info(f"[RAG] Reconstructed {len(docs)} flat RAG documents for '{brand_slug}'")
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Chunking — 500 words, 100-word overlap
# ─────────────────────────────────────────────────────────────────────────────
def _chunk_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunks a single document's content field into 500-word segments with 100-word overlap.
    Each chunk carries its metadata (title, url, source_type, brand).
    """
    content = doc.get("content", "") or ""
    # Clean up whitespace
    content = re.sub(r'\s+', ' ', content).strip()
    words = content.split()

    if not words:
        return []

    title = doc.get("title", "")
    url = doc.get("url", "")
    source_type = doc.get("source_type", "web")
    brand = doc.get("brand", "")

    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP   # 400 words per step
    for i in range(0, len(words), step):
        chunk_words = words[i: i + CHUNK_SIZE]
        if len(chunk_words) < 30:       # skip tiny trailing fragments
            break
        chunk_text = " ".join(chunk_words)
        chunks.append({
            "text": chunk_text,
            "title": title,
            "url": url,
            "source_type": source_type,
            "brand": brand,
            "chunk_index": len(chunks),
        })

    return chunks


def _build_chunks(docs: List[Dict]) -> List[Dict]:
    """Builds all chunks from all docs."""
    all_chunks = []
    for doc in docs:
        all_chunks.extend(_chunk_doc(doc))
    logger.info(f"[RAG] Built {len(all_chunks)} chunks ({CHUNK_SIZE}-word, {CHUNK_OVERLAP}-word overlap)")
    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Embedding — all-MiniLM-L6-v2, 384-dim
# ─────────────────────────────────────────────────────────────────────────────
def _embed_chunks(chunks: List[Dict]):
    """
    Embeds all chunk texts using sentence-transformers.
    Returns numpy array of shape (N, 384).
    """
    import numpy as np
    if not chunks:
        return np.zeros((0, 384), dtype="float32")

    embedder = _get_embedder()
    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, batch_size=64, show_progress_bar=False, convert_to_numpy=True)
    # L2-normalize for cosine similarity via dot product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (norms + 1e-9)
    logger.info(f"[RAG] Embedded {len(chunks)} chunks → shape {embeddings.shape}")
    return embeddings.astype("float32")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Build BM25 index (keyword / sparse retrieval)
# ─────────────────────────────────────────────────────────────────────────────
def _build_bm25(chunks: List[Dict]):
    """Returns a BM25Okapi index over the tokenised chunk texts."""
    from rank_bm25 import BM25Okapi
    tokenised = [c["text"].lower().split() for c in chunks]
    return BM25Okapi(tokenised)


# ─────────────────────────────────────────────────────────────────────────────
# Index cache management
# ─────────────────────────────────────────────────────────────────────────────
def _get_or_build_index(brand_slug: str) -> Optional[Dict]:
    """
    Returns cached index if docs haven't changed, otherwise rebuilds.
    Cache key: brand_slug → { chunks, embeddings, bm25, mtime_hash }
    """
    if not brand_slug:
        return None

    current_hash = _folder_mtime_hash(brand_slug)

    cached = _index_cache.get(brand_slug)
    if cached and cached.get("mtime_hash") == current_hash:
        logger.info(f"[RAG] Cache hit for '{brand_slug}' ({len(cached['chunks'])} chunks)")
        return cached

    logger.info(f"[RAG] Building index for '{brand_slug}' (hash changed or first run)...")
    docs = _load_json_docs(brand_slug)
    if not docs:
        logger.info(f"[RAG] No JSON docs found for '{brand_slug}' — no index built")
        return None

    chunks = _build_chunks(docs)
    if not chunks:
        return None

    embeddings = _embed_chunks(chunks)
    bm25 = _build_bm25(chunks)

    index = {
        "chunks": chunks,
        "embeddings": embeddings,
        "bm25": bm25,
        "mtime_hash": current_hash,
    }
    _index_cache[brand_slug] = index
    logger.info(f"[RAG] Index built and cached for '{brand_slug}'")
    return index


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Hybrid retrieval — Cosine + BM25, fused with RRF
# ─────────────────────────────────────────────────────────────────────────────
def _hybrid_retrieve(query: str, index: Dict, top_k: int = TOP_K) -> List[Dict]:
    """
    Reciprocal Rank Fusion (RRF) of:
      - Dense: cosine similarity between query embedding and chunk embeddings (384-dim)
      - Sparse: BM25 keyword scores

    RRF score = 1/(rank_dense + 60) + 1/(rank_bm25 + 60)
    Returns top_k chunks with their retrieval metadata.
    """
    import numpy as np

    chunks = index["chunks"]
    embeddings = index["embeddings"]  # shape (N, 384)
    bm25 = index["bm25"]
    n = len(chunks)

    if n == 0:
        return []

    # ── Dense: cosine similarity ──────────────────────────────────────────────
    embedder = _get_embedder()
    q_emb = embedder.encode([query], convert_to_numpy=True)
    q_emb = q_emb / (np.linalg.norm(q_emb) + 1e-9)          # L2 normalise
    dense_scores = (embeddings @ q_emb.T).flatten()            # dot product = cosine
    dense_ranks = np.argsort(dense_scores)[::-1]               # highest score first

    # ── Sparse: BM25 keyword ──────────────────────────────────────────────────
    tokenised_query = query.lower().split()
    bm25_scores = bm25.get_scores(tokenised_query)
    bm25_ranks = np.argsort(bm25_scores)[::-1]

    # ── RRF fusion ────────────────────────────────────────────────────────────
    K = 60  # RRF constant
    rrf_scores = {}
    for rank, idx in enumerate(dense_ranks):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rank + K)
    for rank, idx in enumerate(bm25_ranks):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (rank + K)

    sorted_indices = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]

    retrieved = []
    for idx in sorted_indices:
        chunk = dict(chunks[idx])
        chunk["rrf_score"] = round(rrf_scores[idx], 6)
        chunk["dense_score"] = round(float(dense_scores[idx]), 4)
        chunk["bm25_score"] = round(float(bm25_scores[idx]), 4)
        retrieved.append(chunk)

    logger.info(f"[RAG] Retrieved {len(retrieved)} chunks via hybrid RRF for query: '{query[:60]}...'")
    return retrieved


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Format retrieved context for the LLM prompt
# ─────────────────────────────────────────────────────────────────────────────
def _format_context(retrieved_chunks: List[Dict]) -> str:
    """Formats retrieved context into a clean string for the system prompt."""
    if not retrieved_chunks:
        return ""

    parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        source_label = f"{chunk.get('source_type', 'web').upper()}: {chunk.get('title', 'Unknown')}"
        brand_label = f" [{chunk.get('brand', '')}]" if chunk.get("brand") else ""
        url = chunk.get("url", "")
        url_line = f"\n   URL: {url}" if url else ""
        parts.append(
            f"[Source {i} — {source_label}{brand_label}]{url_line}\n{chunk['text']}"
        )

    return "\n\n" + ("─" * 60) + "\n\n".join(parts) + "\n\n" + ("─" * 60)


def _fetch_verified_brand_images(query: str, brand_name: str) -> List[str]:
    """Fetch verified image URLs for a brand query using Tavily API."""
    try:
        from tavily import TavilyClient
        from dotenv import load_dotenv
        load_dotenv()
        load_dotenv("backend/.env")
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            return []
        client = TavilyClient(api_key=api_key)
        short_q = (query or "")[:100].strip()
        res = client.search(
            query=f"{brand_name} {short_q} official logo brand image",
            search_depth="basic",
            max_results=3,
            include_images=True
        )
        images = res.get("images", [])
        valid_images = [img for img in images if isinstance(img, str) and img.startswith("http") and not any(bad in img for bad in ["imgur.com", "placeholder"])]
        return valid_images[:3]
    except Exception as e:
        logger.warning(f"[RAG] Image search failed: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Step 7: System prompt builder
# ─────────────────────────────────────────────────────────────────────────────
def build_system_prompt(
    brand_name: str,
    agent_type: str,
    brand_context: Optional[str],
    formatted_context: str,
) -> str:
    if agent_type == "Competition Analysis":
        base = """You are a Senior Competitive Intelligence Strategist operating inside an automated strategy tool. You convert raw website and Instagram scrape data into a concise, professional, board-ready competitive analysis document. 
You never speculate beyond what the data supports. You output highly readable Markdown formatting. No preamble, no meta-commentary, nothing outside the document itself.

OBJECTIVE
Given the user brand's data and one or more competitor brands' data, produce a complete but lean competitive analysis Markdown file. Every section from the structure below must appear with its header. Prioritize the single sharpest point over multiple redundant points.

OUTPUT FORMAT RULES (STRICT)
- The vast majority of your output must be standard Markdown text, utilizing headers (H2, H3), bullet points, and Markdown Tables.
- Do NOT output a master JSON blob.
- When generating visual charts (like Share of Voice, Pricing, or Scale Signals), you must output a JSON code block tagged with `recharts`. The UI will intercept this and render a rich interactive dashboard chart inline.
- Example Chart Output format:
  ```recharts
  {
    "type": "bar",
    "title": "Pricing Index Comparison",
    "x_label": "Brands & Competitors Analyzed",
    "y_label": "Price Index (Scale 1–10: 1 = Economy, 10 = Luxury/Premium)",
    "description": "Benchmarks commercial pricing tier positioning relative to market rivals.",
    "takeaway": "Brand A commands premium margins at 9/10, while Brand B anchors value adoption at 7/10.",
    "data": [
      { "name": "Brand A", "value": 9 },
      { "name": "Brand B", "value": 7 }
    ]
  }
  ```
- Use `"type": "bar"` for comparative values across brands (like Pricing, Scale, Momentum).
- Use `"type": "pie"` for share-based distributions (like Share of Voice).

DATA HANDLING RULES
- Every claim must trace to evidence in the web scan or Instagram scan. Never invent numbers.
- If a brand has no usable data for a section, state this in one line rather than fabricating content or omitting the section.

COMPARISON TABLE ATTRIBUTES
Output a beautiful Markdown table comparing the user brand and competitors across these rows:
1. Value proposition clarity
2. Brand archetype & tone of voice
3. Product and offer breadth
4. Pricing tier and positioning
5. Differentiation claims
6. Website content depth
7. Search visibility signal strength
8. Instagram content pillars
9. Momentum signal

VISUAL SECTIONS REQUIRED
Generate a `recharts` JSON block (as shown in the format rules) for each of the following:
1. Price Index by brand (type: "bar", value 1-10)
2. Scale Signal by brand (type: "bar", value 1-10)
3. Estimated Share of Voice across all brands (type: "pie", percentages totaling 100)
Provide exactly one takeaway sentence in plain markdown text directly below each chart.

SWOT ANALYSIS
Provide a clean Markdown grid or bulleted list for Strengths, Weaknesses, Opportunities, and Threats for the User Brand. Two to four items per quadrant, one line each.

RECOMMENDATIONS TABLE
Output a Markdown table with 4-5 rows: Recommendation, Finding Based On, Priority (High/Med/Low).

PERSONALIZED NEXT STEPS
Write one short paragraph naming the single biggest gap or opportunity found for the user's brand specifically. Provide a numbered action plan of exactly five actionable steps. End with one line stating the single metric to check in 30-60 days to measure success.
"""
    elif agent_type == "GTM Strategy":
        base = """You are a Chief Marketing Officer & Senior Go-To-Market (GTM) Strategist operating inside an automated strategy tool.
You synthesize raw brand website data, Instagram scrape data, competitor scans, AND the user's specific answers to the 4 GTM setup questions (Objectives, Target Customer/Segment, Growth Constraints, and Business Stage) into a highly visual, board-ready Go-To-Market strategy.

You never speculate beyond what the data and inputs support. You output clean Markdown formatting. No preamble, no meta-commentary, nothing outside the document itself.

OBJECTIVE
Produce an elite, data-backed Go-To-Market Strategy report tailored specifically to the user's business stage, objectives, constraints, and competitive landscape.

OUTPUT FORMAT RULES (STRICT)
- The vast majority of your output must be standard Markdown text, utilizing headers (H2, H3), bullet points, and Markdown Tables.
- Do NOT output a master JSON blob for the whole response.
- Generates RICH DIVERSE VISUAL DASHBOARDS using JSON code blocks tagged with `recharts`. The UI will intercept these blocks and render interactive inline charts.
- Available chart types: `"bar"`, `"line"`, `"area"`, `"radar"`, `"pie"`.

Chart Format Specifications:
1. BAR CHART: `{"type": "bar", "title": "...", "data": [{"name": "Item", "value": 85}, ...]}`
2. TREND / LINE CHART: `{"type": "line", "title": "...", "data": [{"name": "Month 1", "Brand A": 20, "Brand B": 35}, ...], "keys": ["Brand A", "Brand B"]}`
3. AREA GROWTH CHART: `{"type": "area", "title": "...", "data": [{"name": "Q1", "Revenue": 100, "Users": 400}, ...], "keys": ["Revenue", "Users"]}`
4. RADAR COMPETITIVE CHART: `{"type": "radar", "title": "...", "data": [{"subject": "Pricing", "User Brand": 8, "Competitor": 6}, ...], "keys": ["User Brand", "Competitor"]}`
5. PIE SHARE CHART: `{"type": "pie", "title": "...", "data": [{"name": "Segment A", "value": 45}, ...]}`

REQUIRED VISUAL SECTIONS (INCLUDE ALL 5 DIVERSE CHARTS)
You MUST output a `recharts` JSON block for each of the following 5 visual parameters:
1. Target Customer Segment Breakdown (type: "pie", percentage distribution totaling 100)
2. Strategic Capability Radar Matrix (type: "radar", rating 1-10 across Brand Power, Price Flexibility, Digital Presence, Innovation, Distribution for User Brand vs Competitors)
3. 90-Day GTM Growth & Revenue Projection (type: "area" or "line", metrics over time for Month 1, Month 2, Month 3, Month 6)
4. Channel Efficiency vs Cost Index (type: "bar", rating 1-10 for acquisition channels based on user growth constraints)
5. Execution Intensity Ramp-up (type: "bar", intensity score 1-10 across Pre-Launch, Launch Week, Month 1, Scaling)
Provide exactly one short takeaway sentence in plain markdown text directly below each chart.

REQUIRED REPORT SECTIONS
1. EXECUTIVE SUMMARY & POSITIONING STATEMENT
- Summarize GTM goals based on user questionnaire inputs (Objective, Target Customer, Stage).
- Core Value Proposition & Positioning Statement.

2. TARGET AUDIENCE & ICP PROFILES
- Primary ICP profile detailing pain points, buying triggers, and behavioral preferences.
- Secondary segment breakdown.

3. GO-TO-MARKET COMPARATIVE MATRIX
Output a comprehensive Markdown table comparing User Brand vs Competitors across:
- Value Proposition
- Target ICP Focus
- Core Acquisition Channels
- Pricing & Offer Tiering
- Key Messaging Hook

4. PRICING & PACKAGING STRATEGY
Markdown table detailing Tier Name, Target Segment, Price Point, and Value Features.

5. 90-DAY ACTIONABLE GTM ROADMAP
Markdown table detailing Phase (Month 1 / Month 2 / Month 3), Core Milestones, Channel Focus, and Success KPI.

6. METRICS & RISK MITIGATION PLAN
- North Star Metric & secondary KPIs (CAC, LTV, Conversion Rate).
- 3 key growth risks (addressing user's constraints) with concrete countermeasures.
"""
    elif agent_type == "Product Launch Strategy":
        base = """You are a Chief Product Officer (CPO) & Senior VP of Growth Marketing operating inside an automated strategy tool.
You synthesize raw brand website data, Instagram scrape data, competitor scans, AND the user's specific answers to the 3 Product Launch setup questions:
1. Launch Offering ("What are you launching?": e.g., New Product, New Service, New Feature, New Brand, New App, Relaunch)
2. Primary Launch Objective ("What is the primary objective of this launch?": e.g., Generate Sales, Generate Leads, Build Awareness, Acquire Users, Drive Adoption, Enter New Market)
3. Planned Launch Timeline ("What is your planned launch timeline?": e.g., Within 30 Days, 1–3 Months, 3–6 Months, 6–12 Months)

You convert these inputs into an elite, highly personalized, board-ready Product Launch Strategy document specifically tailored to the user's brand, offering type, revenue/sales objectives, and timeline constraints.

You never speculate beyond what the data and inputs support. You output clean Markdown formatting. No preamble, no meta-commentary, nothing outside the document itself.

OBJECTIVE
Produce a master-class, actionable, data-backed Product Launch Strategy report that turns user inputs and brand research into a complete launch execution playbook.

OUTPUT FORMAT RULES (STRICT)
- The vast majority of your output must be standard Markdown text, utilizing headers (H2, H3), bullet points, and Markdown Tables.
- Do NOT output a master JSON blob for the whole response.
- Generates RICH DIVERSE VISUAL DASHBOARDS using JSON code blocks tagged with `recharts`. The UI will intercept these blocks and render interactive inline charts.
- Available chart types: `"bar"`, `"line"`, `"area"`, `"radar"`, `"pie"`.

Chart Format Specifications:
1. BAR CHART: `{"type": "bar", "title": "...", "data": [{"name": "Item", "value": 85}, ...]}`
2. TREND / LINE CHART: `{"type": "line", "title": "...", "data": [{"name": "Month 1", "Brand A": 20, "Brand B": 35}, ...], "keys": ["Brand A", "Brand B"]}`
3. AREA GROWTH CHART: `{"type": "area", "title": "...", "data": [{"name": "Pre-Launch", "Revenue": 0, "Waitlist": 500}, ...], "keys": ["Revenue", "Waitlist"]}`
4. RADAR COMPETITIVE CHART: `{"type": "radar", "title": "...", "data": [{"subject": "Value Prop", "User Brand": 9, "Competitor": 6}, ...], "keys": ["User Brand", "Competitor"]}`
5. PIE SHARE CHART: `{"type": "pie", "title": "...", "data": [{"name": "Teaser Phase", "value": 25}, ...]}`

REQUIRED VISUAL SECTIONS (INCLUDE ALL 5 DIVERSE CHARTS)
You MUST output a `recharts` JSON block for each of the following 5 visual parameters:
1. Launch Budget & Resource Allocation (type: "pie", percentage distribution across Pre-Launch Teaser, Launch Day Blitz, Post-Launch Nurture, Retargeting)
2. Product-Market Competitiveness Radar Matrix (type: "radar", rating 1-10 across Unique Value Prop, Pricing Attractiveness, Digital Presence, Feature Depth, Customer Trust for User Brand vs Competitors)
3. Launch Sales & User Acquisition Trajectory (type: "area" or "line", projected metrics over Pre-Launch, Launch Week, Month 1, Month 2, Month 3 tailored to timeline)
4. Marketing Channel Efficiency vs Conversion ROI (type: "bar", rating 1-10 for acquisition channels prioritized for the user's launch objective)
5. Sprint Execution Intensity & Workload Index (type: "bar", intensity score 1-10 across Week 1-2 Warm-up, Launch Week Peak, Month 1 Optimization, Scaling)
Provide exactly one short takeaway sentence in plain markdown text directly below each chart.

REQUIRED REPORT SECTIONS
1. EXECUTIVE LAUNCH SUMMARY & POSITIONING STATEMENT
- Core Launch Vision & Strategic Objective (referencing user's launch type, objective, and timeline).
- Unique Selling Proposition (USP) & Product Hook for the user's brand.

2. TARGET AUDIENCE & EARLY ADOPTER SEGMENTATION
- Primary ICP profile detailing buying triggers, core pain points solved by this launch, and conversion hooks.
- Early Adopter / VIP segment strategy.

3. COMPETITIVE LAUNCH POSITIONING MATRIX
Markdown table comparing User Product Launch vs Top Competitors across:
- Core Offering / Feature Hook
- Target Customer Focus
- Primary Acquisition Channels
- Pricing / Launch Offer Structure
- Vulnerability / Competitive Gap

4. 3-PHASE LAUNCH EXECUTION ROADMAP
Markdown table detailing:
- Phase (Pre-Launch Teaser / Launch Day Blitz / Post-Launch Growth)
- Key Milestones & Activities
- Channel Focus & Marketing Assets
- Conversion & Sales Targets

5. CAMPAIGN MESSAGING, OFFER & PROMOTION PLAYBOOK
- Launch Messaging Pillars (Hook, Value, Proof, Call-to-Action).
- Special Promotional Structure (e.g. Early-bird Pricing, VIP Waitlist Bonus, Bundle Offer).
- Multi-Channel Content Execution Plan (Email sequence, Social Posts, PR/Influencer outreach).

6. LAUNCH KPIs, METRICS & CONTINGENCY RISK PLAN
- North Star Launch Metric & Secondary Sales/Acquisition KPIs.
- 3 Critical Launch Risks (tailored to user's launch objective and timeline) with concrete risk mitigation countermeasures.
"""
    else:
        base = f"""You are StratAI, an elite AI strategy consultant.

Target Brand: **{brand_name}**
Role/Mode: **{agent_type}**
"""
    if brand_context:
        base += f"\nBrand Context: {brand_context}\n"

    base += """
### STRICT RESPONSE OUTPUT RULES:
1. NO PREAMBLE / NO FILLER INTROS: Begin your response directly with the answer/analysis. FORBIDDEN starting words: "Certainly!", "Sure!", "Here is...", "Based on...", "According to...", "In response to...".
2. NO POSTAMBLE / NO OUTROS: End immediately after your final strategic point. FORBIDDEN ending phrases: "Hope this helps!", "Let me know if you need...", "Feel free to ask...", "In conclusion...".
3. NO INTERNAL JARGON OR META-REFERENCES: NEVER use internal developer or implementation terminology in your outputs. FORBIDDEN words/phrases:
   - "chunk", "chunks", "chunk index"
   - "JSON", "Extracted JSON", "raw JSON"
   - "No Raw Scrape Data", "raw scrape", "scrapped data", "Tavily research", "Instagram scraper", "knowledge base"
4. MISSING DATA HANDLING: If requested information, metric, or detail is missing or not present in the research, state simply and directly: "Data not available" or "Information not available". Do NOT explain why data is missing or mention technical processing.
5. NO FAKE/BROKEN IMAGE LINKS: NEVER output placeholder image links (e.g., imgur.com, placeholder URLs) or meta-notes like "(Note: Replace with actual generated chart...)".
6. CHARTS AND VISUAL GRAPH FORMATTING: For strategy reports (such as GTM Strategy, Product Launch Strategy, or Competition Analysis), you MUST generate all required visual dashboard sections. For general chat queries, generate a visual chart whenever numerical data or visual comparison is relevant. Every visual chart MUST be output as a JSON code block with the language `recharts`.
CRITICAL: Every `recharts` JSON block MUST include the `"type"` field set to one of: `"bar"`, `"line"`, `"area"`, `"radar"`, or `"pie"`.

Example Chart JSON Schemas:
- Bar Chart:
```recharts
{
  "type": "bar",
  "title": "Channel Efficiency Score",
  "x_label": "Marketing & Acquisition Channels",
  "y_label": "Efficiency Score (0–100 Scale)",
  "description": "Evaluates return on investment and customer acquisition velocity across active channels.",
  "takeaway": "SEO yields highest efficiency at 85/100, while Paid Ads requires optimization to lower CAC.",
  "data": [
    {"name": "SEO", "value": 85},
    {"name": "Paid Ads", "value": 60}
  ]
}
```
- Radar Chart:
```recharts
{
  "type": "radar",
  "title": "Competitive Matrix",
  "data": [
    {"subject": "Brand Power", "User Brand": 8, "Competitor": 6},
    {"subject": "Pricing", "User Brand": 7, "Competitor": 9}
  ],
  "keys": ["User Brand", "Competitor"]
}
```
- Area Chart:
```recharts
{
  "type": "area",
  "title": "Revenue & User Growth",
  "data": [
    {"name": "Month 1", "Revenue": 10, "Users": 100},
    {"name": "Month 2", "Revenue": 25, "Users": 280}
  ],
  "keys": ["Revenue", "Users"]
}
```
7. PRESENTATION: Present insights using clean headers, bullet points, markdown tables, and recharts visual blocks. Be concise, direct, strategic, and board-ready.
8. NO RAW HTML TAGS IN TABLES: Do NOT output raw literal string tags like `<br>` or `<br/>`. Format bullet points cleanly on separate lines or with standard markdown list formatting.
9. NO DOLLAR SIGN SYMBOLS FOR PRICING: Do NOT use raw `$$` or `$$$` symbols to represent pricing tiers, as double dollar signs trigger KaTeX math rendering errors. Always write clear, professional text labels like 'Budget Tier', 'Mid-Tier', 'Premium Tier', or 'Luxury Tier'.
"""

    if formatted_context:
        base += f"""
=== RESEARCH CONTEXT ===
{formatted_context}
=== END CONTEXT ===
"""
    else:
        base += (
            "\nNote: Comprehensive research is currently processing. Provide direct strategic insights. "
            "If specific data points are needed and unavailable, state 'Data not available'.\n"
        )
    return base


def _generate_short_title(text: str) -> str:
    """Generate a concise 4-6 word title summarizing the starting conversation."""
    import re
    clean_text = re.sub(r"['’]s\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^\w\s-]', ' ', clean_text).strip()
    stop_words = {
        'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'and', 'or', 'is', 'are', 'was', 'were', 
        'can', 'could', 'you', 'please', 'me', 'what', 'how', 'why', 'where', 'when', 'my', 'i', 'we', 'our', 'give', 'show', 'tell', 'about'
    }
    words = [w for w in cleaned.split() if w.lower() not in stop_words and len(w) > 1]
    if not words:
        words = [w for w in cleaned.split() if len(w) > 1]
    title_words = [w.capitalize() for w in words[:6]]
    if len(title_words) < 4 and len(cleaned.split()) >= 4:
        title_words = [w.capitalize() for w in cleaned.split()[:5]]
    return " ".join(title_words) if title_words else "Strategy Discussion"


# ─────────────────────────────────────────────────────────────────────────────
# Main: Streaming chat with RAG
# ─────────────────────────────────────────────────────────────────────────────
async def stream_chat(
    messages: List[dict],
    project_id: str,
    db,
    provider: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings.
    Full RAG pipeline per request:
      load JSON docs → chunk (500w/100w) → embed (384-dim) → hybrid retrieve (cos+BM25+RRF) → prompt → stream response
    """
    from sqlalchemy.future import select
    from sqlalchemy import func
    from backend.models.project import Project
    from backend.models.brand import BrandConfig
    from backend.models.message import Message

    # ── Load project + brand from DB ─────────────────────────────────────────
    brand_name = "Your Brand"
    agent_type = "StratAI"
    brand_context = None
    brand_slug = None
    project = None

    try:
        proj_result = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_result.scalar_one_or_none()
        if project:
            agent_type = project.agent_type or "StratAI"
            brand_result = await db.execute(
                select(BrandConfig).where(BrandConfig.id == project.brand_config_id)
            )
            brand = brand_result.scalar_one_or_none()
            if brand:
                brand_name = brand.brand_name
                brand_context = brand.brand_context
                brand_slug = brand.brand_slug
    except Exception as e:
        logger.warning(f"[RAG] Could not load project/brand: {e}")

    # ── User message content ───────────────────────────────────────────────────
    user_content = messages[-1]["content"] if messages else ""

    # ── Wait for Web & Instagram research pipeline completion ─────────
    if brand and brand.pipeline_status in ("pending", "running"):
        logger.info(f"[RAG] Research pipeline is '{brand.pipeline_status}' for '{brand_name}'. Waiting for completion before generating AI response...")
        max_wait_seconds = 180  # Wait up to 3 minutes for scraping completion
        waited = 0
        while waited < max_wait_seconds:
            await asyncio.sleep(3)
            waited += 3

            # Re-check status in DB
            status_res = await db.execute(select(BrandConfig.pipeline_status).where(BrandConfig.id == brand.id))
            current_status = status_res.scalar_one_or_none()

            if current_status in ("complete", "completed"):
                logger.info(f"[RAG] Research pipeline completed after {waited}s for '{brand_name}'. Proceeding to RAG generation.")
                break
            elif current_status == "failed":
                logger.warning(f"[RAG] Research pipeline failed after {waited}s for '{brand_name}'. Proceeding with available documents.")
                break
            else:
                # Send SSE status update to keep connection active and maintain 'Thinking ...' UI indicator
                yield f"data: {json.dumps({'type': 'status', 'content': f'Building brand knowledge base... ({waited}s)'})}\n\n"

    # ── Build / retrieve index (cached in memory, rebuilt only on doc changes) ─
    query = user_content
    retrieved_chunks: List[Dict] = []
    formatted_context = ""

    try:
        index = await asyncio.to_thread(_get_or_build_index, brand_slug)
        if index:
            retrieved_chunks = await asyncio.to_thread(_hybrid_retrieve, query, index)
            formatted_context = _format_context(retrieved_chunks)
    except Exception as e:
        logger.warning(f"[RAG] Retrieval failed: {e}")

    # ── Check for image/logo search intent ────────────────────────────────────
    image_keywords = {"logo", "image", "photo", "picture", "icon", "symbol", "visual", "look"}
    query_words = set(re.findall(r'\w+', user_content.lower()))
    if query_words.intersection(image_keywords):
        logger.info(f"[RAG] Image intent detected in query: '{user_content}'. Fetching verified brand images...")
        fetched_images = await asyncio.to_thread(_fetch_verified_brand_images, user_content, brand_name)
        if fetched_images:
            img_section = "\n=== VERIFIED BRAND IMAGES ===\n"
            for idx, img_url in enumerate(fetched_images, 1):
                img_section += f"- {brand_name} Image {idx}: {img_url}\n"
            img_section += "You MUST include the verified image URL(s) above in your response using markdown syntax: `![Brand Logo](URL)`.\n=== END IMAGES ===\n"
            formatted_context += img_section

    # ── Build system prompt ───────────────────────────────────────────────────
    system_prompt = build_system_prompt(brand_name, agent_type, brand_context, formatted_context)

    # ── Prepare messages ──────────────────────────────────────────────────────
    chat_history = []
    for m in messages:
        if m.get("role") in ("user", "assistant"):
            chat_history.append({"role": m["role"], "content": m["content"]})
    if not chat_history:
        chat_history = [{"role": "user", "content": user_content or "Generate strategy report."}]

    # ── Stream response from selected LLM provider ───────────────────────────
    full_response = ""
    try:
        resolved_provider, api_key = _get_llm_provider(provider)

        # Helper runner function to stream from a given provider
        async def _run_stream(prov: str, key: str):
            nonlocal full_response
            if prov == "qwen":
                logger.info(f"[RAG] Streaming response using Qwen API...")
                from openai import OpenAI
                client = OpenAI(
                    api_key=key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
                model_name = os.environ.get("QWEN_MODEL", "qwen-turbo")
                qwen_messages = [{"role": "system", "content": system_prompt}] + chat_history
                response = client.chat.completions.create(
                    model=model_name,
                    messages=qwen_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            text_chunk = delta.content
                            full_response += text_chunk
                            yield text_chunk

            elif prov == "openai":
                logger.info(f"[RAG] Streaming response using OpenAI API...")
                from openai import OpenAI
                client = OpenAI(api_key=key)
                openai_messages = [{"role": "system", "content": system_prompt}] + chat_history
                model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")
                response = client.chat.completions.create(
                    model=model_name,
                    messages=openai_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            text_chunk = delta.content
                            full_response += text_chunk
                            yield text_chunk

            elif prov == "mistral":
                logger.info(f"[RAG] Streaming response using Mistral API...")
                from openai import OpenAI
                client = OpenAI(
                    api_key=key,
                    base_url="https://api.mistral.ai/v1",
                )
                model_name = os.environ.get("MISTRAL_MODEL", "open-mistral-7b")
                mistral_messages = [{"role": "system", "content": system_prompt}] + chat_history
                response = client.chat.completions.create(
                    model=model_name,
                    messages=mistral_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            text_chunk = delta.content
                            full_response += text_chunk
                            yield text_chunk

            else:
                logger.info(f"[RAG] Streaming response using Anthropic API...")
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
                with client.messages.stream(
                    model=anthropic_model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=chat_history
                ) as stream:
                    for text_chunk in stream.text_stream:
                        full_response += text_chunk
                        yield text_chunk

        # Try initial provider, fallback to Mistral if it fails
        try:
            async for token in _run_stream(resolved_provider, api_key):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as prov_err:
            if resolved_provider != "mistral" and os.environ.get("MISTRAL_API_KEY"):
                logger.warning(f"[RAG] Provider '{resolved_provider}' failed ({prov_err}). Falling back to Mistral (open-mistral-7b)...")
                mistral_key = os.environ.get("MISTRAL_API_KEY", "").strip()
                async for token in _run_stream("mistral", mistral_key):
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            else:
                raise prov_err

    except Exception as e:
        logger.error(f"[RAG] AI streaming error: {e}")

        yield f"data: {json.dumps({'type': 'error', 'content': f'AI error: {str(e)}'})}\n\n"
        return

    # ── Save user & assistant messages to DB ONLY on successful generation ───
    if full_response and full_response.strip() and project_id and project_id != "dummy":
        try:
            # 1. Save user message
            if user_content:
                user_msg = Message(project_id=project_id, role="user", content=user_content)
                db.add(user_msg)

            # 2. Save assistant response
            assistant_msg = Message(project_id=project_id, role="assistant", content=full_response)
            db.add(assistant_msg)

            # 3. Update LLM provider used for this chat project
            if project:
                project.llm_provider = resolved_provider

            await db.commit()

            # Auto-update chat title to a 4-6 word summary of starting conversation context
            if project and user_content:
                msg_count_res = await db.execute(select(func.count(Message.id)).where(Message.project_id == project_id))
                msg_count = msg_count_res.scalar() or 0
                generic_titles = {"New Chat", "StratAI", "Competition Analysis", "GTM Strategy", "Social Media Strategy", "Brand Audit", "Auto-created project", brand_name}
                if msg_count <= 2 or project.title in generic_titles:
                    new_title = _generate_short_title(user_content)
                    if new_title:
                        project.title = new_title
                        await db.commit()
        except Exception as e:
            logger.warning(f"[RAG] Failed to save conversation messages: {e}")

