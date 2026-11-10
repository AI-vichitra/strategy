"""
Pipeline Service
================
Orchestrates the full brand research pipeline as a FastAPI BackgroundTask:

  1. Tavily web scrape  → docs/{brand_slug}/{brand}_web.json
  2. Tavily deep dive   → docs/{brand_slug}/{brand}_tavily2.json
                       → docs/{brand_slug}/{competitor}_tavily2.json  (x N)
  3. Social discovery   → find Instagram handles via Tavily
  4. Insta scraper      → docs/{brand_slug}/{handle}_insta.json  (x N)
  5. Update DB          → pipeline_status = "complete"

All documents are saved as structured JSON:
  { title, url, source_type, brand, content }
This format is consumed directly by the RAG knowledge base in ai_service.py.
"""

import os
import sys
import json
import logging
import asyncio
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# Root of the project (two levels up from backend/services/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")


def _make_slug(brand_name: str, brand_id: str) -> str:
    """Create a filesystem-safe slug for the docs folder."""
    clean = re.sub(r'[^\w\s-]', '', brand_name.upper()).strip()
    clean = re.sub(r'[\s-]+', '_', clean)
    return clean


def _get_output_dir(brand_slug: str) -> str:
    path = os.path.join(DOCS_DIR, brand_slug)
    os.makedirs(path, exist_ok=True)
    return path


async def run_brand_research_pipeline(
    brand_config_id: str,
    brand_name: str,
    brand_url: str,
    category: str,
    selected_competitors: List[dict],
    db_session_factory,
):
    """
    Full async pipeline. Designed to run as a FastAPI BackgroundTask.
    db_session_factory is the SQLAlchemy async_sessionmaker.
    """
    from backend.services import tavily_service, connector_service, firecrawl_service, exa_service

    brand_slug = _make_slug(brand_name, brand_config_id)
    output_dir = _get_output_dir(brand_slug)

    logger.info(f"[Pipeline] Starting for brand '{brand_name}' (id={brand_config_id}), docs → {output_dir}")

    # ── Mark as running in DB ─────────────────────────────────────────────────
    await _update_db(db_session_factory, brand_config_id, {
        "pipeline_status": "running",
        "brand_slug": brand_slug,
    })

    # ── Optional connector enrichment: resolve keys if available ─────────────
    # Each lookup is independently wrapped so a failure here never affects the
    # rest of the pipeline — missing/broken key(s) => pure Tavily-only flow.
    brand_user_id: Optional[str] = None
    try:
        brand_user_id = await _get_brand_user_id(db_session_factory, brand_config_id)
    except Exception as e:
        logger.warning(f"[Pipeline] Failed to resolve brand user_id for connector lookups: {e}")
        brand_user_id = None

    firecrawl_key: Optional[str] = None
    if brand_user_id:
        try:
            async with db_session_factory() as session:
                firecrawl_key = await connector_service.get_api_key(
                    session, user_id=brand_user_id, connector_id="firecrawl", env_fallback="FIRECRAWL_API_KEY"
                )
            if firecrawl_key:
                logger.info("[Pipeline] Firecrawl key available — enrichment enabled.")
        except Exception as e:
            logger.warning(f"[Pipeline] Firecrawl key lookup failed, continuing without it: {e}")
            firecrawl_key = None

    exa_key: Optional[str] = None
    if brand_user_id:
        try:
            async with db_session_factory() as session:
                exa_key = await connector_service.get_api_key(
                    session, user_id=brand_user_id, connector_id="exa", env_fallback="EXA_API_KEY"
                )
            if exa_key:
                logger.info("[Pipeline] Exa key available — enrichment enabled.")
        except Exception as e:
            logger.warning(f"[Pipeline] Exa key lookup failed, continuing without it: {e}")
            exa_key = None

    try:
        # ── Step 1: Web scrape brand ──────────────────────────────────────────
        logger.info("[Pipeline] Step 1: Web scraping brand website...")
        await asyncio.to_thread(
            tavily_service.run_web_scrape, brand_name, brand_url, output_dir
        )

        # ── Step 2: Deep dive — brand ─────────────────────────────────────────
        logger.info("[Pipeline] Step 2: Deep diving brand...")
        await asyncio.to_thread(
            tavily_service.run_deep_dive, brand_name, brand_url, category, output_dir
        )

        # ── Step 2b: OPTIONAL Firecrawl enrichment — brand website ───────────
        # No-op unless firecrawl_key was resolved above; failures never fail the pipeline.
        if firecrawl_key and brand_url:
            logger.info("[Pipeline] Step 2b: Firecrawl enrichment for brand website...")
            try:
                fc_content = await asyncio.to_thread(firecrawl_service.scrape_url, brand_url, firecrawl_key)
                if fc_content:
                    _save_firecrawl_doc(output_dir, brand_name, brand_url, fc_content)
            except Exception as e:
                logger.warning(f"[Pipeline] Firecrawl brand enrichment failed: {e}")

        # ── Step 2c: OPTIONAL Exa enrichment — brand semantic search ─────────
        # No-op unless exa_key was resolved above; failures never fail the pipeline.
        if exa_key:
            logger.info("[Pipeline] Step 2c: Exa semantic search for brand...")
            try:
                exa_results = await asyncio.to_thread(
                    exa_service.search_contents,
                    f"{brand_name} market positioning, products, and strategy",
                    exa_key,
                )
                exa_content = _format_exa_results(exa_results)
                if exa_content:
                    _save_exa_doc(output_dir, brand_name, brand_url, exa_content)
            except Exception as e:
                logger.warning(f"[Pipeline] Exa brand enrichment failed: {e}")

        # ── Step 3: Deep dive — each competitor ──────────────────────────────
        for comp in selected_competitors:
            comp_name = comp.get("name", "")
            comp_url = comp.get("website_url") or comp.get("url") or ""
            if not comp_name:
                continue
            logger.info(f"[Pipeline] Step 3: Deep diving competitor '{comp_name}'...")
            await asyncio.to_thread(
                tavily_service.run_deep_dive, comp_name, comp_url, category, output_dir
            )

            # ── OPTIONAL Firecrawl enrichment — competitor website ───────────
            if firecrawl_key and comp_url:
                logger.info(f"[Pipeline] Firecrawl enrichment for competitor '{comp_name}'...")
                try:
                    fc_content = await asyncio.to_thread(firecrawl_service.scrape_url, comp_url, firecrawl_key)
                    if fc_content:
                        _save_firecrawl_doc(output_dir, comp_name, comp_url, fc_content)
                except Exception as e:
                    logger.warning(f"[Pipeline] Firecrawl competitor enrichment failed for '{comp_name}': {e}")

            # ── OPTIONAL Exa enrichment — competitor semantic search ─────────
            if exa_key:
                logger.info(f"[Pipeline] Exa semantic search for competitor '{comp_name}'...")
                try:
                    exa_results = await asyncio.to_thread(
                        exa_service.search_contents,
                        f"{comp_name} products, pricing, and positioning",
                        exa_key,
                    )
                    exa_content = _format_exa_results(exa_results)
                    if exa_content:
                        _save_exa_doc(output_dir, comp_name, comp_url, exa_content)
                except Exception as e:
                    logger.warning(f"[Pipeline] Exa competitor enrichment failed for '{comp_name}': {e}")

        # ── Step 4: Social handle discovery ───────────────────────────────────
        logger.info("[Pipeline] Step 4: Discovering social handles...")
        all_targets = [{"name": brand_name, "is_brand": True}] + [
            {"name": c.get("name", ""), "is_brand": False} for c in selected_competitors if c.get("name")
        ]

        discovered_handles = []
        brand_handle = ""
        for target in all_targets:
            name = target["name"]
            # Check if competitor already has a handle from the confirm step
            if not target["is_brand"]:
                # Look in selected_competitors for pre-discovered handle
                comp_data = next((c for c in selected_competitors if c.get("name") == name), {})
                handle = comp_data.get("handle") or await asyncio.to_thread(
                    tavily_service.find_social_handle, name
                )
            else:
                # For brand, find its handle
                handle = await asyncio.to_thread(tavily_service.find_social_handle, name)
                brand_handle = handle

            if handle:
                discovered_handles.append({"name": name, "handle": handle, "is_brand": target["is_brand"]})
                logger.info(f"[Pipeline] Discovered handle @{handle} for '{name}'")

        # ── Step 5: Instagram scraper ─────────────────────────────────────────
        if discovered_handles:
            logger.info(f"[Pipeline] Step 5: Running Instagram scraper for {len(discovered_handles)} targets...")
            await _run_instagram_scraper(
                handles=discovered_handles,
                output_dir=output_dir,
                brand_slug=brand_slug
            )
        else:
            logger.warning("[Pipeline] Step 5: No handles discovered, skipping Instagram scraper.")

        # ── Step 6: Compile Knowledge Base ────────────────────────────────────
        logger.info("[Pipeline] Step 6: Compiling Knowledge Base...")
        await asyncio.to_thread(_compile_knowledge_base, brand_name, brand_slug, output_dir)

        # ── Update DB: complete ───────────────────────────────────────────────
        update_data = {
            "pipeline_status": "complete",
            "brand_handle": brand_handle,
            "confirmed_competitor_handles": json.dumps([h["handle"] for h in discovered_handles]),
            "social_metrics": "complete",
        }
        await _update_db(db_session_factory, brand_config_id, update_data)
        logger.info(f"[Pipeline] Completed for brand '{brand_name}'")

    except Exception as e:
        logger.error(f"[Pipeline] FAILED for brand '{brand_name}': {e}", exc_info=True)
        await _update_db(db_session_factory, brand_config_id, {"pipeline_status": "failed"})


async def _run_instagram_scraper(handles: List[dict], output_dir: str, brand_slug: str):
    """
    Calls the insta_agent as a subprocess so it can use Playwright safely.
    Falls back gracefully if insta_state.json is missing.
    """
    insta_agent_path = os.path.join(PROJECT_ROOT, "social_scrapper", "insta_scrapper", "insta_agent.py")
    insta_state_path = os.path.join(PROJECT_ROOT, "social_scrapper", "insta_scrapper", "insta_state.json")

    if not os.path.exists(insta_state_path):
        logger.warning("[Pipeline] insta_state.json not found — skipping Instagram scraper.")
        return

    python_exe = os.path.join(PROJECT_ROOT, "backend", "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    urls = []
    for h in handles:
        handle = (h.get("handle") or "").strip()
        if not handle:
            continue
        if handle.startswith("@"):
            handle = handle[1:]
        if not handle.startswith("http"):
            urls.append(f"https://www.instagram.com/{handle}/")
        else:
            urls.append(handle)

    if not urls:
        return

    # Patch the insta_agent to save into our output_dir by passing project-name
    # insta_agent.py saves to docs/project_scrapped/{project_name}_scrapped/
    # We redirect by symlinking or by calling it directly with env override
    cmd = [
        python_exe, insta_agent_path,
        "--project-name", brand_slug,
        *urls
    ]

    logger.info(f"[Pipeline] Running insta_agent: {' '.join(cmd)}")
    try:
        def _exec_subprocess():
            import subprocess
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=300
            )

        res = await asyncio.to_thread(_exec_subprocess)
        if res.returncode == 0:
            logger.info(f"[Pipeline] insta_agent succeeded. Output: {res.stdout[:500]}")
            # Copy any generated files into our unified output_dir
            _merge_insta_output(brand_slug, output_dir)
        else:
            logger.warning(f"[Pipeline] insta_agent exited with {res.returncode}: {res.stderr[:500]}")
    except Exception as e:
        logger.warning(f"[Pipeline] insta_agent subprocess failed: {e}")


def _merge_insta_output(brand_slug: str, output_dir: str):
    """
    Looks for all *_insta.html and *_insta_state.json across possible dirs.
    Merges them into RAG-friendly *_insta.json in output_dir.
    """
    import re
    
    search_dirs = [
        output_dir,
        os.path.join(DOCS_DIR, f"{brand_slug}_scrapped"),
        os.path.join(DOCS_DIR, "project_scrapped", f"{brand_slug}_scrapped"),
    ]

    found_any = False
    for d in search_dirs:
        if not os.path.exists(d): continue
        for fname in os.listdir(d):
            if fname.endswith("_insta.html"):
                found_any = True
                html_path = os.path.join(d, fname)
                prefix = fname.replace("_insta.html", "")
                state_path = os.path.join(d, f"{prefix}_insta_state.json")
                
                try:
                    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw_html = f.read()
                    raw_html = re.sub(r'<style[^>]*>.*?</style>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
                    raw_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
                    text_content = re.sub(r'<[^>]+>', ' ', raw_html)
                    text_content = re.sub(r'\s+', ' ', text_content).strip()

                    metrics = {}
                    if os.path.exists(state_path):
                        try:
                            with open(state_path, "r", encoding="utf-8") as f:
                                metrics = json.load(f)
                        except Exception:
                            pass

                    doc = {
                        "title": f"{prefix.capitalize()} — Instagram Social Analysis",
                        "url": f"https://instagram.com/{prefix.lower()}",
                        "source_type": "social_instagram",
                        "brand": prefix.capitalize(),
                        "metrics": metrics,
                        "content": text_content
                    }

                    out_file = os.path.join(output_dir, f"{prefix.lower()}_insta.json")
                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(doc, f, ensure_ascii=False, indent=2)
                    logger.info(f"[Pipeline] Saved merged Instagram JSON -> {out_file}")
                except Exception as e:
                    logger.error(f"[Pipeline] Failed to process {fname}: {e}")

    if not found_any:
        logger.warning(f"[Pipeline] No _insta.html files found - skipping merge.")


def _save_firecrawl_doc(output_dir: str, brand_name: str, url: str, content: str) -> None:
    """Saves Firecrawl-scraped content in the same JSON doc format Tavily uses, so
    _compile_knowledge_base picks it up alongside the Tavily-sourced documents."""
    clean_name = re.sub(r'[^\w]', '_', brand_name.lower())
    doc = {
        "title": f"{brand_name} — Firecrawl Web Scrape",
        "url": url,
        "source_type": "firecrawl_scrape",
        "brand": brand_name,
        "content": content,
    }
    filepath = os.path.join(output_dir, f"{clean_name}_firecrawl.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        logger.info(f"[Pipeline] Firecrawl content saved to {filepath}")
    except Exception as e:
        logger.error(f"[Pipeline] Failed to save Firecrawl doc for '{brand_name}': {e}")


def _format_exa_results(results: List[dict]) -> str:
    """Flattens Exa's {title, url, text} result list into a single content string."""
    parts = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        text = (r.get("text") or "").strip()
        if not text:
            continue
        header = f"{title} ({url})".strip() if (title or url) else ""
        parts.append(f"{header}\n{text}".strip() if header else text)
    return "\n\n".join(parts)


def _save_exa_doc(output_dir: str, brand_name: str, url: str, content: str) -> None:
    """Saves Exa semantic-search content in the same JSON doc format Tavily/Firecrawl use,
    so _compile_knowledge_base picks it up alongside the other sourced documents."""
    clean_name = re.sub(r'[^\w]', '_', brand_name.lower())
    doc = {
        "title": f"{brand_name} — Exa Semantic Search",
        "url": url,
        "source_type": "exa_search",
        "brand": brand_name,
        "content": content,
    }
    filepath = os.path.join(output_dir, f"{clean_name}_exa.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        logger.info(f"[Pipeline] Exa content saved to {filepath}")
    except Exception as e:
        logger.error(f"[Pipeline] Failed to save Exa doc for '{brand_name}': {e}")


def _compile_knowledge_base(brand_name: str, brand_slug: str, output_dir: str):
    """Compiles all JSON data in output_dir into a single KB file in KNOWLEDGE_BASE/"""
    kb_dir = os.path.join(PROJECT_ROOT, "KNOWLEDGE_BASE")
    os.makedirs(kb_dir, exist_ok=True)
    
    kb_file = os.path.join(kb_dir, f"{brand_slug}_KB.json")
    
    brands_data = {}
    
    if os.path.exists(output_dir):
        for file in sorted(os.listdir(output_dir)):
            if file.endswith(".json"):
                filepath = os.path.join(output_dir, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        
                    b_name = data.get("brand", "Unknown").strip()
                    b_key = b_name.lower()
                    
                    if b_key not in brands_data:
                        brands_data[b_key] = {
                            "NAME": b_name.capitalize(),
                            "URL": data.get("url", ""),
                            "WEB_SCRAPPED": "Data not found",
                            "INSTA_SCRAPPED": "Data not found",
                            # Internal accumulators only — popped before this dict is
                            # written out, so the final KB file shape is unchanged.
                            "_has_deep_dive": False,
                            "_deep_dive_content": "",
                            "_firecrawl_parts": [],
                            "_exa_parts": [],
                        }

                    if not brands_data[b_key]["URL"] and data.get("url"):
                        brands_data[b_key]["URL"] = data.get("url")

                    stype = data.get("source_type", "")
                    if stype == "deep_dive":
                        brands_data[b_key]["_has_deep_dive"] = True
                        brands_data[b_key]["_deep_dive_content"] = data.get("content", "")
                    elif stype == "firecrawl_scrape":
                        fc_content = data.get("content", "")
                        if fc_content:
                            brands_data[b_key]["_firecrawl_parts"].append((data.get("url", ""), fc_content))
                    elif stype == "exa_search":
                        exa_content = data.get("content", "")
                        if exa_content:
                            brands_data[b_key]["_exa_parts"].append((data.get("url", ""), exa_content))
                    elif stype == "social_instagram":
                        brands_data[b_key]["INSTA_SCRAPPED"] = data.get("content", "")

                except Exception as e:
                    logger.error(f"[Pipeline] Error reading {file} for KB: {e}")

    # ── Merge Tavily deep-dive + optional Firecrawl/Exa content into WEB_SCRAPPED ──
    # When neither a Firecrawl nor an Exa doc exists for a brand (no keys / both
    # failed), this is byte-for-byte what the old direct-assignment code produced.
    for b in brands_data.values():
        has_dd = b.pop("_has_deep_dive", False)
        dd_content = b.pop("_deep_dive_content", "")
        fc_parts = b.pop("_firecrawl_parts", [])
        exa_parts = b.pop("_exa_parts", [])

        if not fc_parts and not exa_parts:
            if has_dd:
                b["WEB_SCRAPPED"] = dd_content
            continue

        pieces = []
        if has_dd and dd_content:
            pieces.append(f"[Source: Tavily Deep Dive]\n{dd_content}")
        for fc_url, fc_content in fc_parts:
            label = f"Firecrawl Scrape — {fc_url}" if fc_url else "Firecrawl Scrape"
            pieces.append(f"[Source: {label}]\n{fc_content}")
        for exa_url, exa_content in exa_parts:
            label = f"Exa Semantic Search — {exa_url}" if exa_url else "Exa Semantic Search"
            pieces.append(f"[Source: {label}]\n{exa_content}")

        if pieces:
            b["WEB_SCRAPPED"] = "\n\n".join(pieces)
        elif has_dd:
            b["WEB_SCRAPPED"] = dd_content

    final_output = {}
    main_brand_key = brand_name.lower().strip()
    
    if main_brand_key in brands_data:
        final_output["brand"] = brands_data.pop(main_brand_key)
    else:
        final_output["brand"] = {
            "NAME": brand_name.capitalize(),
            "URL": "",
            "WEB_SCRAPPED": "Deep dive JSON not found",
            "INSTA_SCRAPPED": "Instagram JSON not found"
        }
        
    final_output["competitors"] = list(brands_data.values())
                    
    with open(kb_file, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    logger.info(f"[Pipeline] Compiled Knowledge Base saved to {kb_file}")

async def _get_brand_user_id(session_factory, brand_config_id: str) -> Optional[str]:
    """Resolves the owning user_id for a brand config, for per-user connector lookups."""
    try:
        from sqlalchemy import select
        from backend.models.brand import BrandConfig
        async with session_factory() as session:
            result = await session.execute(
                select(BrandConfig.user_id).where(BrandConfig.id == brand_config_id)
            )
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"[Pipeline] Failed to resolve brand user_id: {e}")
        return None


async def _update_db(session_factory, brand_config_id: str, updates: dict):
    """Update BrandConfig fields in the database."""
    try:
        from sqlalchemy import update
        from backend.models.brand import BrandConfig
        async with session_factory() as session:
            await session.execute(
                update(BrandConfig)
                .where(BrandConfig.id == brand_config_id)
                .values(**updates)
            )
            await session.commit()
    except Exception as e:
        logger.error(f"[Pipeline] DB update failed: {e}")
