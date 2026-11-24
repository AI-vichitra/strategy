# Competitor Flow — Full Trace (Input → Fetch → Store → Use → Output)

Read-only discovery. Every claim below is backed by a `path/to/file:line` reference
taken from the code as it exists on disk. Where something could not be located,
it is marked **not found** rather than inferred.

---

## 0. ASCII flow diagram

```
┌────────────────────────── INPUT (two independent, unreconciled paths) ──────────────────────────┐
│                                                                                                    │
│  PATH A — Brand-setup wizard                      PATH B — Chat / builder (lazy-create)           │
│  frontend/src/app/brand-setup/page.tsx            frontend/src/components/CompetitorForm.tsx      │
│  ad-hoc {name,url} rows, no cap          ───┐     CompetitorDetail{brand_name,website_url,        │
│  POST /api/brands/search-competitors        │     social_media} capped at 5 in the UI             │
│    → tavily_service.search_competitors      │     (CompetitorForm.tsx:133-138)                    │
│    → candidates shown, user confirms        │     mounted only in builder/MainContent.tsx:1831    │
│  POST /api/brands/confirm                   │     POST /api/projects/  → Project.competitor_details│
│    → BrandConfig.competitors (write-only)   │       (routers/projects.py:21,34-41,76,102)          │
│    → Project created (NO competitor_details)│       MAX_COMPETITORS = 5, else HTTP 422              │
│    → background_tasks.add_task(             │                                                      │
│        pipeline_service.run_brand_research_ │     ⚠ no pipeline is ever triggered for this path    │
│        pipeline, selected_competitors=...)  │       (no caller of run_brand_research_pipeline       │
│        (routers/brand.py:124-136)           │        other than routers/brand.py:129)               │
└──────────────────────────────────────────┬──┴──────────────────────────────────────────────────┘
                                            │ (Path A only)
                                            ▼
┌───────────────────────────────── FETCH (pipeline_service.py, sequential) ────────────────────────┐
│  for comp in selected_competitors:                     (pipeline_service.py:148-181)              │
│    tavily_service.run_deep_dive  (always)                                                         │
│    firecrawl_service.scrape_url  (only if a Firecrawl key resolved — optional)                    │
│    exa_service.search_contents   (only if an Exa key resolved — optional)                         │
│  then: Tavily social-handle discovery for brand + every competitor (sequential)                   │
│  then: Instagram scraper subprocess (insta_agent.py) for all discovered handles                    │
│        (only Instagram step uses real concurrency: ≤3 Playwright tabs, insta_agent.py:168)         │
└──────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                            ▼
┌───────────────────────────────── STORE ───────────────────────────────────────────────────────────┐
│  docs/{BRAND_SLUG}/*.json  (one file set per entity: brand + each competitor)                      │
│    {slug}_web.json  {slug}_tavily2.json  {slug}_firecrawl.json  {slug}_exa.json  {handle}_insta.json│
│  _compile_knowledge_base() (pipeline_service.py:415-516) merges these into:                        │
│    KNOWLEDGE_BASE/{BRAND_SLUG}_KB.json  = { "brand": {...}, "competitors": [ {...}, ... ] }         │
│    each entity: { NAME, URL, WEB_SCRAPPED, INSTA_SCRAPPED } — brand and competitor are              │
│    STRUCTURALLY IDENTICAL; only the containing key ("brand" vs "competitors") differs.              │
│  ⚠ "web_scrape" source docs are never merged into WEB_SCRAPPED (see Gaps). No overwrite guard —     │
│    every re-run clobbers the same files in place (no versioning).                                  │
└──────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                            ▼
┌───────────────────────────────── USE (ai_service.py) ─────────────────────────────────────────────┐
│  _load_json_docs() flattens KB → one RAG doc per non-empty WEB_SCRAPPED/INSTA_SCRAPPED field        │
│  _chunk_doc(): 500-word chunks, 100-word overlap  (ai_service.py:33-34,160-194)                     │
│  _get_or_build_index(): ONE mixed index per brand_slug — brand + ALL competitors share one pool      │
│  _hybrid_retrieve(): cosine + BM25 + RRF, TOP_K=6, one query = the user's last chat message          │
│    (no per-competitor retrieval; no filtering by brand name)                                        │
│  _format_context(): each surfaced chunk carries ONE entity-level URL, not a per-source URL           │
│  build_system_prompt(): appends                                                                     │
│    (a) _format_competitor_details(Project.competitor_details) — ONLY ever populated by Path B        │
│    (b) blueprint_service.build_section_prompt("Competition Analysis") → report_blueprints.json       │
│    (c) a second, independently-hardcoded "Competition Analysis" instruction block in ai_service.py   │
└──────────────────────────────────────────┬────────────────────────────────────────────────────────┘
                                            ▼
┌───────────────────────────────── OUTPUT ───────────────────────────────────────────────────────────┐
│  LLM markdown (free text + recharts/brandpalette fenced blocks) — no inline citations required       │
│  slide_planner.plan_section(section_markdown, ...) — operates on markdown TEXT ONLY, no KB access    │
│  pptx_service._add_content_chrome(..., source=None always) → footer slot renders blank today         │
│  export_service.py — no competitor-specific logic; DOCX/PDF/PPTX just carry the generated markdown   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. INPUT

### 1a. Manual entry — Path A: brand-setup wizard

- Frontend form: `frontend/src/app/brand-setup/page.tsx`. Competitor rows are a bare
  `{name, url}` tuple (`page.tsx:58`), added via `handleAddCompetitor` (`page.tsx:80-85`),
  rendered inline at `page.tsx:350-393`. **No cap** is enforced anywhere in this component —
  unlike `CompetitorForm`, there is no `maxCompetitors` here.
- No CSS module dedicated to competitor rows — styling comes from `page.module.css`'s
  general form classes (`competitorRow`, `competitorChip`, etc., referenced at `page.tsx:352-390`;
  not separately inspected since it's layout-only).
- On submit (`handleSubmit`, `page.tsx:123-179`) it POSTs to `/api/brands/search-competitors`
  with `brand_name, website_url, category, user_competitors` (`page.tsx:144-153`).
- Request schema: `BrandSearchRequest` (`backend/schemas/brand.py:41-45`), `user_competitors: List[CompetitorInput]`
  where `CompetitorInput = {name, url}` (`backend/schemas/brand.py:36-38`). No cap in the schema.
- Backend router `search_competitors` (`backend/routers/brand.py:51-72`) calls
  `tavily_service.search_competitors(...)` (`backend/services/tavily_service.py:30-79`), which:
  - runs `web_scrapper/tavily_comp.get_competitors` (`tavily_service.py:47-48`) for Tavily discovery (see 1b),
  - merges in `user_competitors`, deduped **only by case-insensitive name** against Tavily's candidates
    (`tavily_service.py:64-73`) — no URL-based matching,
  - returns `candidates[:8]` (`tavily_service.py:76`) — **the final list is capped to 8**, applied
    *after* the user's entries are appended, so if Tavily already filled the list, user-added
    competitors beyond the first few can be silently dropped by the slice.
- User reviews/edits the merged candidate list in the `confirm_competitors` step
  (`page.tsx:420-567`; state `candidates`, `page.tsx:66`), then POSTs to `/api/brands/confirm`
  with `selected_competitors: [{name, website_url, handle}]` (`page.tsx:195-214`,
  schema `BrandConfirmRequest`/`CompetitorConfirmed` at `backend/schemas/brand.py:49-62`).
- Backend `confirm_brand` (`backend/routers/brand.py:76-138`):
  - writes `BrandConfig.competitors` as a JSON string of `{name, url}` (`routers/brand.py:93-96,103`,
    column defined at `backend/models/brand.py:17`). **This field is write-only** — a repo-wide
    grep for other reads of `BrandConfig.competitors` / `brand.competitors` found no matches; it is
    never read again anywhere in `backend/`.
  - creates the `Project` row **without** setting `competitor_details` (`routers/brand.py:112-119`) —
    confirmed by reading the `Project(...)` constructor call, which only passes
    `user_id, brand_config_id, agent_type, title, description, brand_kit`.
  - launches `pipeline_service.run_brand_research_pipeline` as a `BackgroundTask`, passing
    `selected_competitors` directly as a Python list (`routers/brand.py:124-136`) — this list is
    **not** the same thing as `Project.competitor_details`; it is only ever held in memory for this
    one background task invocation.

Fields captured in Path A: `name`, `website_url` (optional), and a `handle` the user may edit in the
confirm step (`page.tsx:497-503`). **No social-media URL fields** (LinkedIn/Facebook/Twitter/YouTube)
exist in this path — only the chat-path form (`CompetitorForm.tsx`) captures those.

### 1b. Automatic discovery — Tavily competitor search

`web_scrapper/tavily_comp.py:get_competitors` (`tavily_comp.py:9-97`):
- Runs **3 fixed natural-language queries** against Tavily (`tavily_comp.py:24-26`), e.g.
  `"Find top 5 alternatives and direct competitors to the {brand_category} company '{brand_name}' ({brand_url})..."`,
  `search_depth="advanced"`, `include_answer=True` (no `max_results` override, so Tavily's default applies — not found explicitly).
- A "competitor" is decided **purely by domain-frequency voting**: it regex-extracts domain-looking
  tokens out of Tavily's free-text `answer` for each query (`tavily_comp.py:45`), excludes a fixed
  blocklist of directory/news sites (`growjo.com, crunchbase.com, zoominfo.com, linkedin.com, g2.com,
  glassdoor.com, clutch.co, goodfirms.co, forbes.com, bloomberg.com` — `tavily_comp.py:56`) and the
  brand's own domain (`tavily_comp.py:60-61`), then counts domain frequency across the 3 queries and
  keeps the **top 5 most-mentioned domains** (`tavily_comp.py:73-82`). There is no semantic
  verification that the result is actually a competitor and not, e.g., a supplier or press outlet
  that merely co-occurred in the answer text.
- The candidate's `name` is derived from the domain itself (`domain.split('.')[0].capitalize()`,
  `tavily_comp.py:86`), not from any verified brand name — e.g. `dlf.in` → `"Dlf"`.
- Brand's own Instagram handle is separately discovered via `web_scrapper/tavily_insta.get_insta_handle`
  (`tavily_service.py:58-59`, implementation at `tavily_insta.py:7-42`): a single
  `'"{brand_name}" site:instagram.com'` query, `search_depth="basic"`, `max_results=5`, picks the
  first URL matching `instagram.com/<handle>` that isn't a known non-profile path
  (`tavily_insta.py:36`).
- Validation/dedup against the manual list: see 1a above — name-only, case-insensitive, and the
  combined list is truncated to 8 regardless of source.

### 1c. Chat lazy-create — Path B

- Frontend form: `frontend/src/components/CompetitorForm.tsx`, CSS module
  `frontend/src/components/CompetitorForm.module.css` (styling only, not detailed here). Mounts
  exactly once, inside the builder chat UI: `frontend/src/components/builder/MainContent.tsx:1831`
  (`<CompetitorForm competitors={competitors} onChange={setCompetitors} />`).
- Cap: `maxCompetitors = 5` default prop (`CompetitorForm.tsx:133`), enforced client-side at
  `CompetitorForm.tsx:138` (`if (competitors.length >= maxCompetitors) return;`).
- Fields captured per competitor (`CompetitorForm.tsx:5-17`): `brand_name` (required),
  `website_url` (optional), and `social_media: {linkedin, instagram, facebook, twitter, youtube}`
  (all optional, collapsible section at `CompetitorForm.tsx:99-125`).
- State lives in `MainContent.tsx:603` and is populated from the active project on load:
  `setCompetitors(Array.isArray(proj.competitor_details) ? proj.competitor_details : [])`
  (`MainContent.tsx:1053`).
- When the user sends a chat message with no existing project, `MainContent.tsx:1173-1190` POSTs
  to `/api/projects/` with `competitor_details: competitors.filter(c => c.brand_name.trim())`
  (`MainContent.tsx:1181-1184`) — immediately followed by a POST to `/api/chat/`
  (`MainContent.tsx:1212-1220`). **No research/fetch pipeline is triggered in this path** — see
  Gaps & risks.
- Backend `create_project` (`backend/routers/projects.py:74-106`): `_serialize_competitor_details`
  (`projects.py:34-41`) re-validates the cap server-side (`MAX_COMPETITORS = 5`, `projects.py:21`;
  raises HTTP 422 above that) and JSON-serializes the list into `Project.competitor_details`
  (column: `backend/models/project.py:22`). The same serializer is reused by `update_project`
  (`projects.py:131-148`) for `PUT /api/projects/{id}`.

### Manual-vs-automatic / Path-A-vs-Path-B summary

| | Path A (brand-setup wizard) | Path B (chat/builder) |
|---|---|---|
| Entry point | `POST /api/brands/confirm` | `POST /api/projects/` |
| Competitor storage | `BrandConfig.competitors` (write-only, never read again) | `Project.competitor_details` (read by `_format_competitor_details`) |
| Social-media URLs captured? | No | Yes (5 platforms) |
| Cap | None in schema/router; Tavily auto-discovery caps its own candidate list to 8 | 5, enforced both client- and server-side |
| Fetch/scrape triggered? | Yes — `pipeline_service.run_brand_research_pipeline` | **No** — no caller found |
| Reaches the LLM prompt via `_format_competitor_details`? | **No** — `Project.competitor_details` is never set on this path | Yes |
| Reaches the LLM via RAG (KB)? | Yes, if the pipeline ran and succeeded | No — nothing ever populates `KNOWLEDGE_BASE/*` for this path's competitors |

So competitor data is collected on **both** paths, but each path only feeds **one** of the two
downstream mechanisms (RAG-via-KB vs. prompt-injection-via-`competitor_details`), and the two
mechanisms are never cross-wired.

---

## 2. FETCH

Orchestrated entirely by `backend/services/pipeline_service.py:run_brand_research_pipeline`
(`pipeline_service.py:46-236`), invoked only from `routers/brand.py:129` (grep-confirmed single caller).

### Loop shape — sequential, not parallel

`for comp in selected_competitors:` (`pipeline_service.py:148`) — each competitor's Tavily deep dive,
optional Firecrawl scrape, and optional Exa search are awaited one after another via
`await asyncio.to_thread(...)` (`pipeline_service.py:154,162,172`) **inside** the loop body; there is
no `asyncio.gather` or any other concurrency primitive across competitors. The same is true of the
brand's own steps (1 and 2, lines 109-145) and of the social-handle-discovery loop
(`pipeline_service.py:191-207`, `for target in all_targets`). The **only** real concurrency in the
whole competitor pipeline is inside the Instagram-scraper subprocess, which caps itself at 3
concurrent Playwright tabs (`social_scrapper/insta_scrapper/insta_agent.py:168`) — but that subprocess
itself is invoked once, synchronously awaited, from the pipeline (`pipeline_service.py:212`,
`_run_instagram_scraper` at `pipeline_service.py:239-299`).

### Per-competitor services

| Service | Gated on key? | Optional/no-op without key? | Failure behaviour | Retry/backoff/timeout |
|---|---|---|---|---|
| Tavily deep dive (`tavily_service.run_deep_dive`, `tavily_service.py:139-184`, called at `pipeline_service.py:154-156`) | `TAVILY_API_KEY` env var (`tavily_service.py:21-26`) | No — required; raises `RuntimeError` inside `_get_client()` if missing, but `run_deep_dive` wraps the whole body in `try/except Exception` and logs+returns `None` (`tavily_service.py:182-184`) | Silent skip (logged `error`), pipeline continues | None found — single call, no retry, no explicit timeout param to the Tavily client |
| Firecrawl scrape (`firecrawl_service.scrape_url`, `firecrawl_service.py:23-45`, called at `pipeline_service.py:162`) | A Firecrawl key must resolve via `connector_service.get_api_key` (DB connector or `FIRECRAWL_API_KEY` env fallback — `pipeline_service.py:82-92`) | Yes — the whole Firecrawl block is skipped if `firecrawl_key` is falsy (`pipeline_service.py:159`) | Returns `None` on any exception (`firecrawl_service.py:43-45`); caller additionally wraps the call in its own `try/except` (`pipeline_service.py:161-166`) | `SCRAPE_TIMEOUT = 60`s (`firecrawl_service.py:18`), single attempt, no retry/backoff |
| Exa semantic search (`exa_service.search_contents`, `exa_service.py:20-48`, called at `pipeline_service.py:172-176`) | Exa key must resolve the same way (`pipeline_service.py:94-105`) | Yes — skipped if `exa_key` falsy (`pipeline_service.py:169`) | Returns `[]` on any exception (`exa_service.py:46-48`); caller also wraps in `try/except` (`pipeline_service.py:171-181`) | `REQUEST_TIMEOUT = 30`s (`exa_service.py:17`), single attempt, no retry |
| `web_scrapper/` (`tavily_web.run_report`, called via `tavily_service.run_deep_dive` → `tavily_service.py:152`) | Same `TAVILY_API_KEY` | No — required | Same as Tavily deep dive row; `run_report` itself logs and returns an empty answer per failed category query rather than aborting (`tavily_web.py:544-546`) | 4 categorized queries, `search_depth="advanced"`, `max_results=5` each (`tavily_web.py:531-546`); no retry |
| `social_scrapper/insta_scrapper/insta_agent.py` (Instagram) | Needs `social_scrapper/insta_scrapper/insta_state.json` to exist (a saved login/session state); skipped entirely otherwise (`pipeline_service.py:247-249`) | Yes — pure no-op without that state file | Non-zero subprocess exit code → logged `warning`, pipeline continues (`pipeline_service.py:296-297`); per-profile `asyncio.TimeoutError` after 90s is caught and logged (`insta_agent.py:109-115`) | 90s per-profile timeout (`insta_agent.py:110`), 300s overall subprocess timeout (`pipeline_service.py:288`), ≤3 concurrent tabs (`insta_agent.py:168`), no retry |
| Handle discovery (`tavily_service.find_social_handle` → `tavily_insta.get_insta_handle`) | `TAVILY_API_KEY` | No — required | Returns `""` on any exception (`tavily_insta.py:41-42`, `tavily_service.py:201-203`) | Single `max_results=5`, `search_depth="basic"` call, no retry |

`firecrawl_service.crawl_site` (the v2 `/map` + multi-page scrape helper, `firecrawl_service.py:49-76`)
is **defined but never called** anywhere in `backend/` (grep-confirmed) — dead code; only the
single-page `scrape_url` is used.

### Character/token caps on fetched content

**None found.** Neither `firecrawl_service.scrape_url` nor `exa_service.search_contents` nor
`tavily_service.run_deep_dive`/`run_web_scrape` truncate their returned `content`/`text` before
writing it to disk. This is empirically confirmed by the live data in `KNOWLEDGE_BASE/BHARTI_KB.json`:
the brand entity's `WEB_SCRAPPED` field is **1,274,769 characters**, and one competitor
(`Max estate`) is **1,169,604 characters** — see §4 Data provenance and Gaps & risks.

---

## 3. STORE

### Per-brand/per-competitor file layout on disk

Confirmed live against `docs/BHARTI/` (the directory actually produced by a real pipeline run):

```
docs/{BRAND_SLUG}/
  {slug}_web.json        — run_web_scrape output (tavily_service.py:83-135)
  {slug}_tavily2.html    — raw deep-dive HTML report (tavily_web.py:549-558)
  {slug}_tavily2.json    — stripped-text version of the above (tavily_service.py:139-184)
  {slug}_firecrawl.json  — optional, only if Firecrawl key resolved (pipeline_service.py:361-378)
  {slug}_exa.json        — optional, only if Exa key resolved (pipeline_service.py:395-412)
  {handle}_insta.json    — optional, only if Instagram scraping succeeded (pipeline_service.py:302-355)
```
One such set per entity — the brand itself, plus one set per selected competitor, all inside the
same `docs/{BRAND_SLUG}/` directory (`_make_slug`/`_get_output_dir`, `pipeline_service.py:33-43`).
`{slug}` is `brand_name.replace(" ", "_").lower()` for the Tavily deep-dive filename
(`tavily_service.py:174`) but `re.sub(r'[^\w]', '_', brand_name.lower())` for the web-scrape/Firecrawl/Exa
filenames (`tavily_service.py:96`, `pipeline_service.py:364,398`) — two slightly different slugging
functions are used for different files of the *same* entity.

### KNOWLEDGE_BASE JSON shape

`_compile_knowledge_base` (`pipeline_service.py:415-516`) writes `KNOWLEDGE_BASE/{BRAND_SLUG}_KB.json`:

```json
{
  "brand": { "NAME": "...", "URL": "...", "WEB_SCRAPPED": "...", "INSTA_SCRAPPED": "..." },
  "competitors": [ { "NAME": "...", "URL": "...", "WEB_SCRAPPED": "...", "INSTA_SCRAPPED": "..." }, ... ]
}
```
Confirmed against the live files `KNOWLEDGE_BASE/AMUL_KB.json` and `KNOWLEDGE_BASE/BHARTI_KB.json`.
**The brand's own entry and a competitor's entry are structurally identical** — the same four keys,
the same internal accumulation logic (`pipeline_service.py:432-465`) — the *only* distinguishing
factor downstream is which top-level key (`"brand"` vs an element of `"competitors"`) an entity sits
under.

`WEB_SCRAPPED` is assembled by concatenating, in order: the Tavily deep-dive text (if any) labelled
`"[Source: Tavily Deep Dive]\n{content}"`, then each Firecrawl part labelled
`"[Source: Firecrawl Scrape — {url}]\n{content}"`, then each Exa part labelled
`"[Source: Exa Semantic Search — {url}]\n{content}"` (`pipeline_service.py:470-497`) — but **only**
when at least one Firecrawl or Exa part exists; if neither key was configured, `WEB_SCRAPPED` is just
the raw deep-dive text with no label at all (`pipeline_service.py:479-482,496-497`). If no deep-dive
doc was found either, it stays at its initialized default, `"Data not found"`
(`pipeline_service.py:439`) — confirmed live: `KNOWLEDGE_BASE/AMUL_KB.json`'s first competitor has
`WEB_SCRAPPED == "Data not found"`.

### Overwrite vs. versioning

No versioning of any kind. `_get_output_dir` reuses the same deterministic path for a given
`brand_config_id` every run (`pipeline_service.py:40-43`), and every file write in this module and
in `tavily_service.py`/`firecrawl_service.py`/`exa_service.py` opens its target with mode `"w"`
(plain overwrite) — e.g. `pipeline_service.py:374,407`, `tavily_service.py:132,176`. Re-running the
pipeline for the same brand silently replaces all prior competitor data with no history, diff, or
backup.

### DB columns involved

- `BrandConfig.competitors` (`backend/models/brand.py:17`) — JSON list of `{name, url}`, write-only (see §1a).
- `BrandConfig.confirmed_competitor_handles` (`backend/models/brand.py:22`) — JSON list of discovered
  handles, written once at `pipeline_service.py:228`. A repo-wide grep for other reads of this column
  found no matches — also effectively write-only today.
- `Project.competitor_details` (`backend/models/project.py:22`) — JSON list of `CompetitorDetail`
  objects, read by `_format_competitor_details` (see §4) and by the frontend on project load
  (`MainContent.tsx:1053`).
- `BrandConfig.brand_slug` (`backend/models/brand.py:20`) — the key that ties a chat session's RAG
  index to the pipeline's output folder (`pipeline_service.py:68`, read at `ai_service.py:2395`).

---

## 4. USE — how competitors reach the LLM

### 4a. `_format_competitor_details` — prompt-injection helper

`backend/services/ai_service.py:386-431`. Called once, at `ai_service.py:2453`
(`build_system_prompt(..., competitor_details)`), with `competitor_details = project.competitor_details`
read at `ai_service.py:2452`. Because `Project.competitor_details` is **only ever populated on Path B**
(§1c), **this block renders for Path-A-created projects only if the user later edits competitors
through the chat builder** — a fresh brand-setup-wizard project has `competitor_details = None`, so
`_format_competitor_details` returns `""` immediately (`ai_service.py:390-391`) and the block never
appears.

When it does fire, the rendered block looks like:
```
## USER-PROVIDED COMPETITOR INFORMATION
The user has identified the following competitors. Use these as PRIMARY competitors in your analysis.
Research each competitor using the provided URLs for accurate, current information.

### Competitor 1: <brand_name>
- Website: <website_url>
- LinkedIn: <...>
- Instagram: <...>
...

IMPORTANT: These user-provided competitors MUST be included in the Competitive Landscape section. ...
```
(`ai_service.py:399-430`). Note the instruction "Research each competitor using the provided URLs" is
purely a prompt directive to the LLM — the backend performs no actual fetch of those URLs at this
point; the model either already has the relevant knowledge, pulls it from whatever RAG context is
separately attached, or fabricates it.

When there are zero competitors (`None`/empty list/invalid JSON), `_format_competitor_details`
returns `""` (`ai_service.py:390-397`) and `build_system_prompt` simply omits the block
(`ai_service.py:2262-2263` — the `if competitor_block:` guard).

### 4b. RAG indexing

`backend/services/ai_service.py`:
- KB load: `_load_json_docs` (`ai_service.py:111-154`) flattens `KNOWLEDGE_BASE/{brand_slug}_KB.json`
  into one RAG "document" per non-empty `WEB_SCRAPPED`/`INSTA_SCRAPPED` field, across **both** the
  brand and every competitor (`ai_service.py:144-148`) — brand and competitor content go into the
  **same flat list**, distinguished only by a `"brand"` metadata field carrying the entity's `NAME`.
- Chunking: 500-word chunks, 100-word overlap, uniform for brand and competitor content alike
  (`CHUNK_SIZE`/`CHUNK_OVERLAP` at `ai_service.py:33-34`, `_chunk_doc` at `ai_service.py:160-194`).
- Index: one `_get_or_build_index(brand_slug)` per brand (`ai_service.py:241-277`) — **not** split
  per-competitor; all of a brand's competitor chunks live in the same embedding/BM25 index as the
  brand's own chunks.
- Retrieval: `_hybrid_retrieve` (`ai_service.py:283-333`) runs **once per chat turn**, querying with
  the user's latest message text (`query = user_content`, `ai_service.py:2426,2433`), fusing dense
  cosine similarity and BM25 via Reciprocal Rank Fusion, returning the global top `TOP_K = 6` chunks
  (`ai_service.py:35`) from the mixed pool — there is no mechanism to force retrieval of a specific
  named competitor's chunks; if a competitor's content is semantically distant from the user's
  wording it may simply not surface, however good the original scrape was.
- `_format_context` (`ai_service.py:339-354`) renders each surfaced chunk with ONE `url` (the
  entity-level `URL` field) and a `[brand]` label — not the finer-grained per-source URL that may be
  embedded inside the chunk's own text as a `[Source: ...]` label (see §5 Data provenance).

### 4c. Agent-side prompts

- `build_system_prompt` (`ai_service.py:434-2335`) branches on `agent_type == "Competition Analysis"`
  (`ai_service.py:441`) into a large hardcoded instruction block including required chart types
  (`ai_service.py:2212-2217`) and **REQUIRED REPORT SECTIONS**: Competitive Landscape Map, Competitor
  Deep Profiles, Positioning & Messaging Comparison, Strengths/Weaknesses Battlecard, Win/Loss Themes,
  CI Monitoring Plan (`ai_service.py:2219-2236`).
- Independently, every `build_system_prompt` call (regardless of branch) also appends
  `blueprint_service.build_section_prompt(agent_type)` (`ai_service.py:2251-2255`), which pulls from
  `backend/config/report_blueprints.json`: the 5 `common_sections` (one of which, order 3, is literally
  `"Competitive Landscape"` — `report_blueprints.json`/`common_sections[3]`) plus, for this agent
  specifically, `agent_blueprints["competition-analysis"]`'s `type_specific_sections`:
  `competitor_deep_dive`, `competitive_strategy`, `action_plan`
  (confirmed by reading `backend/config/report_blueprints.json` directly). The kebab-case key is
  produced from `agent_type` by `blueprint_service.py:33` (`re.sub(r"[\s_]+", "-", agent_key.strip().lower())`).
- These two sources (the hardcoded block and the JSON blueprint) were never reconciled — they define
  **two separate, overlapping section structures** for the same report (see Gaps & risks).
- Other agent prompts referencing competitors: the generic (non-"Competition Analysis") branch
  (`ai_service.py:2238-2243`) still receives `_format_competitor_details`'s block if present
  (`ai_service.py:2261-2263`, unconditional on `agent_type`), and the shared
  `"NEVER use placeholder names like 'Competitor X'..."` instruction (`ai_service.py:2256`) applies to
  every agent type.

---

## 5. OUTPUT — competitors in the report

### Blueprint sections that are competitor-driven

- `common_sections[3]`: `"competitive_landscape"` / "Competitive Landscape" — required for every
  agent type (`report_blueprints.json`, `common_sections`).
- `agent_blueprints["competition-analysis"].type_specific_sections`: `competitor_deep_dive`
  ("Competitor Deep Dive" — individual profiles, SWOT, competitive advantages),
  `competitive_strategy` ("Competitive Strategy" — differentiation, response plan), `action_plan`
  (generic, not competitor-specific) — all confirmed directly from `report_blueprints.json`.
- No **Positioning Map** component or blueprint key was found by name anywhere in
  `backend/config/report_blueprints.json` or `backend/services/slide_planner.py` — **not found**.
  The closest equivalents are the hardcoded "Competitive Positioning Matrix" `recharts` radar chart
  instruction (`ai_service.py:2214`) and the blueprint's plain-text "Market Positioning" subsection
  under `competitive_landscape` (`common_sections[3].subsections`).

### Exports beyond markdown

`backend/services/export_service.py` contains **no competitor-specific logic at all** (grep-confirmed
zero matches for "competitor" in that file) — DOCX/PDF/PPTX exports carry over whatever markdown
prose/tables/charts the LLM produced, with no special-casing for competitor-sourced content versus
brand content.

### Slide-planner grounding check

`backend/services/slide_planner._is_grounded` (`slide_planner.py:497-536`) applies the **same**
numeric-claim/hedge-word check to `stat_row` and `timeline` components regardless of whether their
figures are about the brand or a competitor (`slide_planner.py:508-515` — no branch on entity).
Critically, the check validates a slide's numeric claims against `source_text`, which is **the
report's own already-generated section markdown**, not the original Tavily/Firecrawl/Exa documents —
so "grounding" here means "this number also appears verbatim in this section's prose," not "this
number is traceable to a cited source URL." A fabricated-but-internally-consistent competitor
statistic would pass this check just as easily as a real one.

### Slide-chrome source footer

`backend/services/pptx_service._add_content_chrome` accepts an optional `source` parameter rendered
into a small footer textbox (`pptx_service.py:378-381`, geometry `chrome["footer"]`). Its own docstring
states plainly: *"a small source-FOOTER slot at the bottom — renders `source` when given, else stays
blank (real source extraction is a follow-up; this just builds the slot)"* (`pptx_service.py:334-336`).
A grep across `backend/services/pptx_service.py` for `source=` found **zero call sites** passing a
value — every slide's footer renders blank today. Confirmed genuinely unreachable, not merely unused:
`slide_planner.plan_section` (`slide_planner.py:335-...`) takes only `section_markdown`, `section_title`,
and `tpl` as input — the planner never receives the RAG `retrieved_chunks` or their per-chunk `url`
metadata, so even if `pptx_service` were wired to accept a source string, nothing upstream of it
currently carries a URL forward from the KB into slide generation.

---

## 6. Data provenance — full chain of custody for one competitor value

Trace a single sentence that ends up in a finished report, e.g. a pricing claim about a competitor
sourced from a Firecrawl scrape of their pricing page:

1. **Origin**: Firecrawl's `/scrape` endpoint returns Markdown for a specific competitor URL
   (`firecrawl_service.scrape_url`, `firecrawl_service.py:23-45`). At this point the URL is known
   precisely (it's the function's own `url` argument).
2. **First write**: `pipeline_service._save_firecrawl_doc` writes `{slug}_firecrawl.json` with
   `{"title": ..., "url": url, "source_type": "firecrawl_scrape", "brand": comp_name, "content": fc_content}`
   (`pipeline_service.py:361-378`) — URL still precisely attached, per-document.
3. **Compilation into the KB**: `_compile_knowledge_base` folds this document's `content` into the
   competitor's single `WEB_SCRAPPED` string, prefixed with an inline text label
   `"[Source: Firecrawl Scrape — {url}]\n"` (`pipeline_service.py:488-489`). **This is the first loss
   point**: the URL survives only as plain prose text *inside* the blob, not as structured metadata
   attached to the specific sentences that follow it. If a second Firecrawl page or an Exa result is
   also folded in, its own `[Source: ...]` label is simply concatenated after — nothing marks where
   one source's content ends and the next begins except that label text.
4. **RAG document reconstruction**: `_load_json_docs` re-wraps the *entire* `WEB_SCRAPPED` blob
   (all sources concatenated) as one `"deep_dive"`-typed RAG document, with a single `url` field taken
   from the entity's top-level `URL` (the competitor's homepage, not the specific pricing-page URL)
   (`ai_service.py:122-131`). **Second loss point**: the specific Firecrawl URL from step 1 is now
   indistinguishable, at the metadata level, from the generic homepage URL — the only place the real
   URL still exists is as buried text that may or may not survive intact.
5. **Chunking**: `_chunk_doc` slides a blind 500-word/100-word-overlap window over the full blob
   (`ai_service.py:160-194`). **Third loss point**: the `[Source: Firecrawl Scrape — {url}]` label and
   the sentence it introduces can land in different chunks, or the label can be split mid-string, if
   the window boundary falls between them. There is no sentence- or source-aware chunking.
6. **Retrieval**: if this particular chunk wins the top-6 RRF ranking for the user's query
   (`ai_service.py:283-333`), it is surfaced to the LLM with the entity-level `url` (homepage) as its
   only structured source reference (`_format_context`, `ai_service.py:339-354`).
7. **Generation**: the LLM writes the pricing claim into Markdown. Nothing in
   `build_system_prompt`'s **STRICT RESPONSE OUTPUT RULES** (`ai_service.py:2266-2322`) instructs it to
   cite a source URL inline, and no rule forbids it either — citation is simply never requested.
   **Fourth loss point**: even the one surviving entity-level URL is typically not carried into the
   visible output unless the model happens to mention it unprompted.
8. **Slide planning**: `slide_planner.plan_section` receives only the generated Markdown text for that
   section (`slide_planner.py:335`) — no chunk metadata, no URLs, nothing from the KB.
9. **Slide chrome**: `pptx_service._add_content_chrome`'s `source` footer parameter is never populated
   by any caller (`pptx_service.py:378-381`, zero call sites pass `source=`).
10. **Export**: `export_service.py` has no competitor/source-specific handling; whatever is in the
    Markdown (by now, no URL) is what ships in DOCX/PDF/PPTX.

**Where the URL is lost, concretely**: step 3 (`pipeline_service.py:488-489`) is where a precise,
per-source URL is first demoted from structured data to incidental prose text; step 4
(`ai_service.py:122-131`) is where it is further collapsed to one generic entity-level URL; by step 7
even that generic URL is not reliably reaching the rendered output. The slide/export stages (8-10)
were never built to carry a URL at all — the pptx footer slot exists but was explicitly left
unwired (`pptx_service.py:334-336`).

---

## 7. External services table

| Service | File | Trigger condition | Failure behaviour | Caps / limits |
|---|---|---|---|---|
| Tavily — competitor discovery | `web_scrapper/tavily_comp.py:9-97` | Path A, on `POST /api/brands/search-competitors` | Per-query exceptions swallowed (`tavily_comp.py:65-66`); empty answer list → `get_competitors` returns `[]` (`tavily_comp.py:68-70`) | 3 fixed queries; keeps top 5 domains by frequency (`tavily_comp.py:82`); final candidate list capped to 8 after merging user entries (`tavily_service.py:76`) |
| Tavily — brand/competitor web scrape | `tavily_service.run_web_scrape`, `tavily_service.py:83-135` | Pipeline Step 1 (brand only) | Per-query exceptions logged + skipped (`tavily_service.py:119-120`); missing key → logged error, returns `None` (`tavily_service.py:91-93`) | 5 fixed queries, `max_results=3` each; no content truncation |
| Tavily — deep dive | `tavily_service.run_deep_dive` → `web_scrapper/tavily_web.run_report`, `tavily_web.py:485-558` | Pipeline Steps 2 & 3 (brand + every competitor) | Whole call wrapped in `try/except`, returns `None` on failure (`tavily_service.py:182-184`); per-category query failures logged individually (`tavily_web.py:544-546`) | 4 categorized queries, `max_results=5`, `search_depth="advanced"`; no content truncation |
| Tavily — social handle discovery | `tavily_service.find_social_handle` → `web_scrapper/tavily_insta.py:7-42` | Pipeline Step 4, brand + every competitor without a pre-supplied handle | Returns `""` on any exception (`tavily_insta.py:41-42`) | `max_results=5`, `search_depth="basic"`, single query |
| Firecrawl v2 `/scrape` | `firecrawl_service.scrape_url`, `firecrawl_service.py:23-45` | Only if a Firecrawl key resolves (DB connector or `FIRECRAWL_API_KEY` env), brand + every competitor with a URL | Returns `None` on any exception; caller also catches and logs (`pipeline_service.py:161-166`) | 60s timeout (`firecrawl_service.py:18`); no retry; no content truncation |
| Firecrawl v2 `/map` (`crawl_site`) | `firecrawl_service.py:49-76` | **Never called** | n/a | n/a — dead code |
| Exa `/search` | `exa_service.search_contents`, `exa_service.py:20-48` | Only if an Exa key resolves, brand + every competitor | Returns `[]` on any exception; caller also catches and logs (`pipeline_service.py:171-181`) | 30s timeout (`exa_service.py:17`); `numResults=5` default; no content truncation |
| Instagram scraper (`insta_agent.py`, Playwright) | `social_scrapper/insta_scrapper/insta_agent.py` via `pipeline_service._run_instagram_scraper`, `pipeline_service.py:239-299` | Only if `insta_state.json` exists and ≥1 handle discovered | Non-zero exit → logged warning, pipeline continues; per-profile timeout caught (`insta_agent.py:109-115`) | 90s per profile, 300s subprocess-wide, ≤3 concurrent tabs (`insta_agent.py:168`) |

---

## 8. Gaps & risks

- **Dead/unused data**: `BrandConfig.competitors` (`backend/models/brand.py:17`) and
  `BrandConfig.confirmed_competitor_handles` (`backend/models/brand.py:22`) are each written exactly
  once and never read again anywhere in `backend/` (grep-confirmed). `backend/scripts/add_competitor_details.py`
  is a one-off migration script, not part of the runtime flow.
- **Dead code**: `firecrawl_service.crawl_site` (`firecrawl_service.py:49-76`) — the only multi-page
  Firecrawl capability — is never invoked; only single-page `scrape_url` is used.
- **Silent data loss in KB compilation**: `run_web_scrape`'s output (`source_type: "web_scrape"`,
  `tavily_service.py:125`, including its structured per-result `sources` array, `tavily_service.py:118`)
  is read by `_compile_knowledge_base` only far enough to seed the entity's `NAME`/`URL`
  (`pipeline_service.py:432-450`); the `if/elif` chain that fills `WEB_SCRAPPED`
  (`pipeline_service.py:452-465`) has no branch for `stype == "web_scrape"`, so its `content` and
  `sources` are **silently discarded**. Only `deep_dive`/`firecrawl_scrape`/`exa_search`/
  `social_instagram` typed docs ever reach the KB's text fields.
- **No character/token caps anywhere in the fetch→store chain**: confirmed empirically — a live KB
  file (`KNOWLEDGE_BASE/BHARTI_KB.json`) has a brand `WEB_SCRAPPED` field of 1,274,769 characters and
  a competitor (`Max estate`) field of 1,169,604 characters. These get chunked into hundreds of
  500-word RAG chunks each, diluting the odds that any single relevant chunk wins the top-6 retrieval
  for a given query, and ballooning embedding/index build time per chat turn (index is rebuilt
  whenever the docs-folder mtime hash changes, `ai_service.py:241-277`).
- **Chat-path competitors are never fetched at all**: `run_brand_research_pipeline` has exactly one
  caller (`routers/brand.py:129`); `create_project`/`update_project` in `routers/projects.py` never
  invoke any fetch/scrape logic. A competitor added through `CompetitorForm` in the chat builder is
  persisted to `Project.competitor_details` and injected into the prompt as a *name + URL + social
  links* instruction (`_format_competitor_details`), but the model is simply told to "research" it —
  there is no corresponding KB entry, no RAG chunks, and no actual outbound fetch of the provided
  URLs. This is a materially different (and materially weaker) data pipeline than the wizard path,
  with no indication to the user that the two are not equivalent.
- **Wizard-path competitors never produce a `_format_competitor_details` block**: because
  `confirm_brand` never writes `Project.competitor_details` (`routers/brand.py:112-119`), the explicit
  "MUST be included" prompt instruction (`ai_service.py:427-430`) never fires for wizard-created
  projects — those competitors reach the model only indirectly, via whatever RAG chunks happen to be
  retrieved, with no hard mandate that they appear in the output at all.
- **Two independent, unreconciled definitions of the "Competition Analysis" report structure**: a
  large hardcoded section list inside `ai_service.py` (`ai_service.py:2219-2236`) and the JSON
  blueprint's `agent_blueprints["competition-analysis"]` + `common_sections` (`report_blueprints.json`)
  are both appended to the same system prompt (`ai_service.py:2255,2261-2263`) without any attempt to
  merge or de-duplicate overlapping sections (e.g., "Competitive Landscape Map" vs. the blueprint's
  "Competitive Landscape").
- **Unused captured fields**: `CompetitorDetail.social_media` (LinkedIn/Facebook/Twitter/YouTube URLs,
  `CompetitorForm.tsx:5-11`, `backend/schemas/project.py:25-28`) is rendered into the prompt text
  (`ai_service.py:413-424`) but is never passed to any scraper, fetch service, or the pipeline — it
  exists purely as LLM-prompt decoration, never validated as a real URL, never fetched.
- **No validation that a "discovered" competitor is actually a competitor**: Tavily discovery
  (`tavily_comp.py`) accepts any sufficiently-frequently-mentioned domain from free-text search
  answers; there's no check that the result is in the same category/vertical as the brand, nor any
  minimum-confidence threshold.
- **Dedup between manual and discovered competitors is name-only**: `tavily_service.py:64-73`
  matches on lowercased exact name; a user entering `"DLF Ltd"` when Tavily already surfaced
  `"Dlf"` (derived from `dlf.in`) would **not** be deduped, producing two separate candidate rows for
  the same company.
- **No overwrite protection / versioning**: every pipeline re-run for the same `brand_config_id`
  silently replaces all prior `docs/{slug}/*.json` and `KNOWLEDGE_BASE/{slug}_KB.json` content with no
  backup, diff, or audit trail (`pipeline_service.py:40-43` + every `open(..., "w")` call in the module).
- **Slide-chrome source footer is a built-but-unwired stub, not a missing feature discovered
  independently** — the code's own docstring already flags it as a known follow-up
  (`pptx_service.py:334-336`), and even if wired today, no URL metadata survives far enough upstream
  (slide_planner never receives RAG chunk metadata) to populate it meaningfully for competitor claims
  specifically.
- **Grounding check doesn't check against source truth**: `_is_grounded` (`slide_planner.py:497-536`)
  only cross-checks a slide's numbers against the *same report's own markdown prose*, not against the
  original scraped documents — a confidently fabricated-but-self-consistent competitor statistic
  passes exactly like a verified one.

---

## 9. Questions for Moody

1. Is it intentional that chat-path (`CompetitorForm`) competitors never trigger any fetch/scrape —
   i.e., is the chat builder meant to rely entirely on the model's background knowledge plus whatever
   the wizard-path pipeline already populated for that `brand_slug`, rather than running its own
   research? The code gives no indication either way.
2. Should `BrandConfig.competitors` and `Project.competitor_details` be the same field? Right now a
   user can set competitors in the wizard (stored on `BrandConfig`, which drives the actual fetch) and
   *separately* set different competitors in the chat builder (stored on `Project`, which drives the
   prompt-injection block) for the same brand, with no reconciliation. Which one should win, or should
   they be merged?
3. Is the 8-candidate cap in `tavily_service.search_competitors` (`tavily_service.py:76`) intended to
   apply *after* merging in user-provided competitors (potentially crowding them out), or should
   user-provided entries be exempt from that cap?
4. Is the complete absence of content-length caps on Firecrawl/Exa/Tavily deep-dive output
   (observed: >1.2M characters for a single competitor) a known/accepted cost, or should a cap be
   added before this ships to more clients? It directly affects RAG index build time and chunk-pool
   size per chat turn.
5. Was the dual "Competition Analysis" section-structure (hardcoded in `ai_service.py` vs. the JSON
   blueprint) a deliberate layering (e.g., blueprint as a generic skeleton, hardcoded block as
   agent-specific override), or should one of them be retired?
6. Is a "Positioning Map" section/component meant to exist somewhere and just hasn't been built yet,
   or was that terminology from an external spec that doesn't map to anything in this codebase today?
   Nothing matching that name was found in `report_blueprints.json` or `slide_planner.py`.
7. For the slide-chrome source footer: given that no URL metadata currently survives past the
   Markdown-generation step, is "real source extraction" (per the code's own TODO comment) expected to
   mean re-threading RAG chunk URLs all the way through `slide_planner`, or re-deriving sources after
   the fact by searching the KB for matching text? The two approaches have very different implications
   for the architecture.
