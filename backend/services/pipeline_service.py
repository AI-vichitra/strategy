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
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

# Root of the project (two levels up from backend/services/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")


def _make_slug(brand_name: str, project_id: str) -> str:
    """Create a filesystem-safe slug for the docs folder.
    Keyed on project_id so each project gets its own isolated folder and KB file.
    Uses first 8 hex chars of the project_id as a compact, stable suffix.
    """
    clean = re.sub(r'[^\w\s-]', '', brand_name.upper()).strip()
    clean = re.sub(r'[\s-]+', '_', clean)
    pid_short = re.sub(r'[^0-9a-fA-F]', '', project_id)[:8]
    return f"{clean}_{pid_short}" if pid_short else clean


def _get_output_dir(brand_slug: str) -> str:
    path = os.path.join(DOCS_DIR, brand_slug)
    os.makedirs(path, exist_ok=True)
    return path


_ACTIVE_PIPELINE_BRAND_IDS: set = set()


def is_pipeline_active(brand_config_id: str) -> bool:
    """Returns True if a background research pipeline is actively running in this process."""
    return bool(brand_config_id and brand_config_id in _ACTIVE_PIPELINE_BRAND_IDS)


async def run_brand_research_pipeline(
    brand_config_id: str,
    brand_name: str,
    brand_url: str,
    category: str,
    selected_competitors: List[dict],
    db_session_factory,
    project_id: str = "",
):
    """
    Full async pipeline. Designed to run as a FastAPI BackgroundTask.
    db_session_factory is the SQLAlchemy async_sessionmaker.
    """
    _ACTIVE_PIPELINE_BRAND_IDS.add(brand_config_id)
    from backend.services import tavily_service, connector_service, firecrawl_service, exa_service
    from backend.schemas.brand import extract_instagram_username

    brand_slug = _make_slug(brand_name, project_id or brand_config_id)
    output_dir = _get_output_dir(brand_slug)
    _pipeline_started_at = time.monotonic()
    _competitor_names = [c.get("name", "") for c in selected_competitors if c.get("name")]

    logger.info(
        f"[Pipeline] Starting for brand '{brand_name}' (id={brand_config_id}) slug='{brand_slug}' "
        f"competitors={len(_competitor_names)} {_competitor_names} -> docs → {output_dir}"
    )

    # ── Mark as running in DB ─────────────────────────────────────────────────
    await _update_db(db_session_factory, brand_config_id, {
        "pipeline_status": "running",
        "brand_slug": brand_slug,
    })
    logger.info(f"[Pipeline] DB updated: pipeline_status='running' (brand_config_id={brand_config_id})")

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
        _web_scrape_result = await asyncio.to_thread(
            tavily_service.run_web_scrape, brand_name, brand_url, output_dir
        )
        logger.info(f"[Pipeline] Step 1 done: web scrape {'saved' if _web_scrape_result else 'empty/failed'} for '{brand_name}'")

        # ── Step 2: Deep dive — brand ─────────────────────────────────────────
        logger.info("[Pipeline] Step 2: Deep diving brand...")
        _deep_dive_result = await asyncio.to_thread(
            tavily_service.run_deep_dive, brand_name, brand_url, category, output_dir
        )
        logger.info(f"[Pipeline] Step 2 done: deep dive {'saved' if _deep_dive_result else 'empty/failed'} for '{brand_name}'")

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

        # ── Step 2d: Risk & depth research — brand ───────────────────────────
        logger.info("[Pipeline] Step 2d: Risk & depth research for brand...")
        _risk_result = await asyncio.to_thread(
            tavily_service.run_risk_research, brand_name, brand_url, category, output_dir
        )
        logger.info(f"[Pipeline] Step 2d done: risk research {'saved' if _risk_result else 'empty/failed'} for '{brand_name}'")
        _depth_result = await asyncio.to_thread(
            tavily_service.run_depth_research, brand_name, brand_url, category, output_dir
        )
        logger.info(f"[Pipeline] Step 2d done: depth research {'saved' if _depth_result else 'empty/failed'} for '{brand_name}'")

        # ── Step 3: Deep dive — each competitor ──────────────────────────────
        _n_competitors = len(_competitor_names)
        for _comp_idx, comp in enumerate(selected_competitors, start=1):
            comp_name = comp.get("name", "")
            comp_url = comp.get("website_url") or comp.get("url") or ""
            if not comp_name:
                continue
            logger.info(f"[Pipeline] Step 3: competitor {_comp_idx}/{_n_competitors} = '{comp_name}' — deep diving...")
            _comp_dd_result = await asyncio.to_thread(
                tavily_service.run_deep_dive, comp_name, comp_url, category, output_dir
            )
            logger.info(f"[Pipeline] Step 3 done: deep dive {'saved' if _comp_dd_result else 'empty/failed'} for '{comp_name}'")

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

            # ── Risk & depth research — competitor ────────────────────────────
            logger.info(f"[Pipeline] Risk & depth research for competitor '{comp_name}'...")
            _comp_risk_result = await asyncio.to_thread(
                tavily_service.run_risk_research, comp_name, comp_url, category, output_dir
            )
            logger.info(f"[Pipeline] Risk research {'saved' if _comp_risk_result else 'empty/failed'} for '{comp_name}'")
            _comp_depth_result = await asyncio.to_thread(
                tavily_service.run_depth_research, comp_name, comp_url, category, output_dir
            )
            logger.info(f"[Pipeline] Depth research {'saved' if _comp_depth_result else 'empty/failed'} for '{comp_name}'")
            # ── Competitor logo scrape ─────────────────────────────────────────
            if comp_url and not comp.get("logo_url"):
                try:
                    from backend.services import logo_scraper_service
                    # Guard: don't scrape if competitor URL matches brand URL
                    if comp_url.strip().rstrip("/") != (brand_url or "").strip().rstrip("/"):
                        c_logo = await asyncio.to_thread(logo_scraper_service.scrape_and_save_logo, comp_url, comp_name)
                        if c_logo:
                            comp["logo_url"] = c_logo
                except Exception as e:
                    logger.debug(f"[Pipeline] Competitor logo scrape attempt for '{comp_name}': {e}")

            logger.info(f"[Pipeline] Step 3: competitor {_comp_idx}/{_n_competitors} = '{comp_name}' — done.")

        # ── Step 4: Social handle discovery ───────────────────────────────────
        logger.info("[Pipeline] Step 4: Discovering social handles...")
        all_targets = [{"name": brand_name, "is_brand": True}] + [
            {"name": c.get("name", ""), "is_brand": False} for c in selected_competitors if c.get("name")
        ]

        # MERGE, never overwrite: a social_handles["instagram"] the user already
        # confirmed (at onboarding, or by a prior pipeline run) must survive
        # this step untouched — only an absent instagram entry gets filled in.
        existing_social_handles = await _get_brand_social_handles(db_session_factory, brand_config_id)
        existing_instagram = existing_social_handles.get("instagram") or ""

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
                if existing_instagram:
                    # Already confirmed — reuse it, skip rediscovery entirely.
                    handle = extract_instagram_username(existing_instagram)
                else:
                    handle = await asyncio.to_thread(tavily_service.find_social_handle, name)
                brand_handle = handle

            if handle:
                discovered_handles.append({"name": name, "handle": handle, "is_brand": target["is_brand"]})
                logger.info(f"[Pipeline] Discovered handle @{handle} for '{name}'")

        logger.info(f"[Pipeline] Step 4 done: {len(discovered_handles)}/{len(all_targets)} social handles discovered.")

        # brand_handle column stays in sync with social_handles["instagram"];
        # only fill the instagram key here if it was missing before.
        merged_social_handles = dict(existing_social_handles)
        if brand_handle and not existing_instagram:
            merged_social_handles["instagram"] = f"https://instagram.com/{brand_handle}"

        # ── Step 5: Instagram scraper ─────────────────────────────────────────
        if discovered_handles:
            logger.info(f"[Pipeline] Step 5: Running Instagram scraper for {len(discovered_handles)} targets...")
            await _run_instagram_scraper(
                handles=discovered_handles,
                output_dir=output_dir,
                brand_slug=brand_slug
            )
            logger.info("[Pipeline] Step 5 done: Instagram scraper finished.")
        else:
            logger.warning("[Pipeline] Step 5: No handles discovered, skipping Instagram scraper.")

        # ── Step 6: Compile Knowledge Base ────────────────────────────────────
        logger.info("[Pipeline] Step 6: Compiling Knowledge Base...")
        reference_docs = await _get_brand_reference_docs(db_session_factory, brand_config_id)
        kb_json_str = await asyncio.to_thread(_compile_knowledge_base, brand_name, brand_slug, output_dir, reference_docs, selected_competitors)
        await _update_db(db_session_factory, brand_config_id, {"kb_json": kb_json_str})
        logger.info(f"[Pipeline] Step 6 done: kb_json persisted to DB ({len(kb_json_str)} chars) for brand_config_id={brand_config_id}")

        # ── Update DB: complete ───────────────────────────────────────────────
        competitors_with_logos = json.dumps([
            {
                "name": c.get("name", ""),
                "url": c.get("website_url") or c.get("url") or "",
                "logo_url": c.get("logo_url") or ""
            }
            for c in selected_competitors if c.get("name")
        ])
        update_data = {
            "pipeline_status": "complete",
            "competitors": competitors_with_logos,
            "brand_handle": brand_handle,
            "social_handles": json.dumps(merged_social_handles) if merged_social_handles else None,
            "confirmed_competitor_handles": json.dumps([h["handle"] for h in discovered_handles]),
            "social_metrics": "complete",
        }
        await _update_db(db_session_factory, brand_config_id, update_data)
        _elapsed = time.monotonic() - _pipeline_started_at
        logger.info(f"[Pipeline] Completed for brand '{brand_name}' in {_elapsed:.1f}s (brand_config_id={brand_config_id})")

    except Exception as e:
        _elapsed = time.monotonic() - _pipeline_started_at
        logger.error(f"[Pipeline] FAILED for brand '{brand_name}' after {_elapsed:.1f}s: {e}", exc_info=True)
        await _update_db(db_session_factory, brand_config_id, {"pipeline_status": "failed"})
    finally:
        _ACTIVE_PIPELINE_BRAND_IDS.discard(brand_config_id)


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


def _normalize_comp_name(name: str) -> str:
    """Normalize competitor name for comparison: lowercase, strip all non-alphanumeric."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _compile_knowledge_base(brand_name: str, brand_slug: str, output_dir: str, reference_docs: Optional[List[dict]] = None, selected_competitors: Optional[List[dict]] = None) -> str:
    """Compiles all JSON data in output_dir into a single KB file in KNOWLEDGE_BASE/
    (local cache) and returns the same JSON as a string so the caller can persist
    it to BrandConfig.kb_json, the source of truth on an ephemeral filesystem."""
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
                            "_risk_parts": [],
                            "_depth_parts": [],
                            "_risk_sources": [],
                            "_depth_sources": [],
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
                    elif stype == "risk_research":
                        risk_content = data.get("content", "")
                        if risk_content:
                            brands_data[b_key]["_risk_parts"].append((data.get("url", ""), risk_content))
                            brands_data[b_key]["_risk_sources"].extend(data.get("sources", []) or [])
                    elif stype == "depth_research":
                        depth_content = data.get("content", "")
                        if depth_content:
                            brands_data[b_key]["_depth_parts"].append((data.get("url", ""), depth_content))
                            brands_data[b_key]["_depth_sources"].extend(data.get("sources", []) or [])
                    elif stype == "social_instagram":
                        brands_data[b_key]["INSTA_SCRAPPED"] = data.get("content", "")

                except Exception as e:
                    logger.error(f"[Pipeline] Error reading {file} for KB: {e}")

    # ── Merge Tavily deep-dive + optional Firecrawl/Exa content into WEB_SCRAPPED ──
    # When neither a Firecrawl nor an Exa doc exists for a brand (no keys / both
    # failed), this is byte-for-byte what the old direct-assignment code produced.
    #
    # Risk and depth research are kept as their OWN fields (RISK_RESEARCH /
    # DEPTH_RESEARCH below), NOT folded into WEB_SCRAPPED. They used to be
    # appended here too, last — but ai_service._chunk_doc's per-source
    # MAX_KB_CHARS_PER_SOURCE cap truncates WEB_SCRAPPED from the front, so for
    # any entity whose deep-dive/Firecrawl/Exa content alone exceeds that cap
    # (e.g. a brand with 750K+ chars of deep-dive content), risk/depth sat past
    # the cutoff and were silently deleted before chunking ever ran — the
    # entity's own critical evidence never reached the index. Keeping them as
    # separate fields means they're chunked independently, each with their own
    # full cap budget, regardless of how large WEB_SCRAPPED is.
    for b in brands_data.values():
        has_dd = b.pop("_has_deep_dive", False)
        dd_content = b.pop("_deep_dive_content", "")
        fc_parts = b.pop("_firecrawl_parts", [])
        exa_parts = b.pop("_exa_parts", [])
        risk_parts = b.pop("_risk_parts", [])
        depth_parts = b.pop("_depth_parts", [])
        risk_sources = b.pop("_risk_sources", [])
        depth_sources = b.pop("_depth_sources", [])

        if not fc_parts and not exa_parts:
            if has_dd:
                b["WEB_SCRAPPED"] = dd_content
        else:
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

        if risk_parts:
            b["RISK_RESEARCH"] = "\n\n".join(
                f"[Source: {f'Risk & Reputation Research — {u}' if u else 'Risk & Reputation Research'}]\n{c}"
                for u, c in risk_parts
            )
        if depth_parts:
            b["DEPTH_RESEARCH"] = "\n\n".join(
                f"[Source: {f'Depth & Specificity Research — {u}' if u else 'Depth & Specificity Research'}]\n{c}"
                for u, c in depth_parts
            )
        # The per-query search results' own (title, url) pairs — these are the
        # REAL, specific source links the content above was built from (e.g. the
        # exact Trustpilot review page, not just the brand's own website). Kept
        # alongside RISK_RESEARCH/DEPTH_RESEARCH so a citing model — and the
        # deterministic Sources section — can reference the real page a fact
        # came from, never a guessed or generic one. Deduped by URL.
        if risk_sources:
            seen, deduped = set(), []
            for s in risk_sources:
                u = (s or {}).get("url", "")
                if u and u not in seen:
                    seen.add(u)
                    deduped.append({"title": s.get("title", ""), "url": u})
            if deduped:
                b["RISK_RESEARCH_SOURCES"] = deduped
        if depth_sources:
            seen, deduped = set(), []
            for s in depth_sources:
                u = (s or {}).get("url", "")
                if u and u not in seen:
                    seen.add(u)
                    deduped.append({"title": s.get("title", ""), "url": u})
            if deduped:
                b["DEPTH_RESEARCH_SOURCES"] = deduped

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

    # ── Fold in uploaded reference documents — brand only, highest-trust source,
    # so they lead WEB_SCRAPPED ahead of the Tavily/Firecrawl/Exa content. ──────
    if reference_docs:
        from backend.services import reference_service
        ref_blocks = []
        for doc in reference_docs:
            ref_id = doc.get("ref_id")
            filename = doc.get("filename", "")
            if not ref_id:
                continue
            # DB-backed text (saved at confirm time) is the source of truth on an
            # ephemeral filesystem; disk is only a fallback for rows saved before
            # this column existed.
            text = doc.get("text") or reference_service.load_reference_text(ref_id)
            if text:
                ref_blocks.append(f"[Source: Reference Document — {filename}]\n{text}")
        if ref_blocks:
            existing = final_output["brand"].get("WEB_SCRAPPED", "")
            final_output["brand"]["WEB_SCRAPPED"] = "\n\n".join(ref_blocks) + "\n\n" + existing

    # Filter to only the competitors confirmed for this run; normalised name match
    # prevents stale files from prior pipeline runs (different competitor set) leaking in.
    if selected_competitors:
        selected_norm = {_normalize_comp_name(c.get("name", "")) for c in selected_competitors}
        kept, dropped = [], []
        for entry in brands_data.values():
            norm = _normalize_comp_name(entry.get("NAME", ""))
            if norm in selected_norm:
                kept.append(entry)
            else:
                dropped.append(entry.get("NAME", "?"))
        logger.info(f"[Pipeline] KB compile: {len(kept)} of {len(brands_data)} competitors kept after selection filter")
        if dropped:
            logger.info(f"[Pipeline] KB compile: dropped stale competitors (not in this run's selection): {dropped}")
        final_output["competitors"] = kept
    else:
        final_output["competitors"] = list(brands_data.values())
                    
    kb_json_str = json.dumps(final_output, ensure_ascii=False, indent=2)
    with open(kb_file, "w", encoding="utf-8") as f:
        f.write(kb_json_str)
    _n_competitors = len(final_output.get("competitors", []))
    logger.info(
        f"[Pipeline] Compiled Knowledge Base saved to {kb_file} "
        f"({len(kb_json_str)} chars, 1 brand + {_n_competitors} competitors)"
    )
    return kb_json_str

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


async def _get_brand_reference_docs(session_factory, brand_config_id: str) -> Optional[List[dict]]:
    """Resolves the brand's uploaded reference_docs (JSON list of {ref_id, filename}),
    or None if there are none / lookup fails — regression-safe for brands without
    any uploaded reference documents."""
    try:
        from sqlalchemy import select
        from backend.models.brand import BrandConfig
        async with session_factory() as session:
            result = await session.execute(
                select(BrandConfig.reference_docs).where(BrandConfig.id == brand_config_id)
            )
            row = result.first()
            raw = row[0] if row else None
            return json.loads(raw) if raw else None
    except Exception as e:
        logger.error(f"[Pipeline] Failed to resolve brand reference_docs: {e}")
        return None


async def _get_brand_social_handles(session_factory, brand_config_id: str) -> dict:
    """Resolves the brand's current social_handles JSON ({platform: url}), or
    {} if unset / unparseable / lookup fails — the read side of the Step 4
    merge, so a user-confirmed handle is never silently rediscovered."""
    try:
        from sqlalchemy import select
        from backend.models.brand import BrandConfig
        async with session_factory() as session:
            result = await session.execute(
                select(BrandConfig.social_handles).where(BrandConfig.id == brand_config_id)
            )
            row = result.first()
            raw = row[0] if row else None
            parsed = json.loads(raw) if raw else {}
            return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        logger.error(f"[Pipeline] Failed to resolve brand social_handles: {e}")
        return {}


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
