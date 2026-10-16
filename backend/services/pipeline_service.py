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
    from backend.services import tavily_service

    brand_slug = _make_slug(brand_name, brand_config_id)
    output_dir = _get_output_dir(brand_slug)

    logger.info(f"[Pipeline] Starting for brand '{brand_name}' (id={brand_config_id}), docs → {output_dir}")

    # ── Mark as running in DB ─────────────────────────────────────────────────
    await _update_db(db_session_factory, brand_config_id, {
        "pipeline_status": "running",
        "brand_slug": brand_slug,
    })

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
                            "INSTA_SCRAPPED": "Data not found"
                        }
                        
                    if not brands_data[b_key]["URL"] and data.get("url"):
                        brands_data[b_key]["URL"] = data.get("url")
                        
                    stype = data.get("source_type", "")
                    if stype == "deep_dive":
                        brands_data[b_key]["WEB_SCRAPPED"] = data.get("content", "")
                    elif stype == "social_instagram":
                        brands_data[b_key]["INSTA_SCRAPPED"] = data.get("content", "")
                        
                except Exception as e:
                    logger.error(f"[Pipeline] Error reading {file} for KB: {e}")
                    
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
