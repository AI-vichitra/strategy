# StratAI

Multi-agent AI strategy report generator — ask a question, pick a strategy agent, get a branded, export-ready report.

## Overview

StratAI turns a brand's own data (website, Instagram, competitor scans) plus a short questionnaire into a board-ready strategy report, written by one of 31 specialized AI agents (Brand Positioning, Competition Analysis, SEO Strategy, GTM Strategy, and more). Reports are structured markdown with inline interactive charts, editable section-by-section in the UI, and exportable as fully brand-themed PPTX, DOCX, and PDF files that all look identical to each other and to the on-screen version.

## Key Features

- **Multi-agent system** — 31 agents across 6 categories (Digital Strategy, Brand Strategy, Performance Marketing, Strategy & Planning, Competitive Intelligence, Legal & Ops), each with its own system prompt and required-sections/required-charts contract
- **Config-driven report blueprints** — a shared section structure (Executive Summary, Market Context, Consumer Landscape, Competitive Landscape, Key Insights) plus agent-specific sections for 6 report types, with a sensible default blueprint for the rest
- **Brand Kit theming** — upload a logo + pick brand colors, and every export (PPTX/DOCX/PDF) re-themes around it; falls back to an LLM-extracted color palette, then to a built-in per-agent-type theme
- **Competitor details input** — add competitors manually or let the research pipeline auto-detect them via Tavily web search
- **Research pipeline** — background job that scrapes the brand's site (Tavily), runs a deep-dive pass, discovers and scrapes Instagram (Playwright), and indexes everything into a RAG store (sentence-transformers embeddings + BM25) that the agents retrieve from while writing
- **Charts, on-screen and in exports** — bar / line / area / radar / pie / scatter, rendered live with Recharts in the browser and re-rendered identically with matplotlib at export time (never a screenshot)
- **Export suite** — PPTX (python-pptx), DOCX (python-docx), and PDF (DOCX converted via headless LibreOffice) — all brand-themed and visually consistent
- **Shareable public report links** — a revocable, unguessable token link to view a report with no login required
- **Connectors** — users can store their own API keys (Firecrawl, Exa) for optional research enrichment, encrypted at rest

## Tech Stack

**Frontend**
- Next.js 16.2.9 (App Router, Turbopack), React 19.2.4, TypeScript
- Recharts 3.10 (on-screen charts), react-markdown + remark-gfm + rehype-raw (report rendering)
- Plain CSS Modules for styling (no Tailwind/UI framework)
- `@react-oauth/google` for Google Sign-In

**Backend**
- FastAPI, Uvicorn
- SQLAlchemy 2.0 (async) + aiosqlite — SQLite database (`backend/stratai.db`)
- python-docx, python-pptx, matplotlib — export generation
- LibreOffice (headless, via subprocess) — DOCX → PDF
- sentence-transformers + rank-bm25 — RAG retrieval over scraped brand research
- Playwright (Chromium) — Instagram scraping
- Tavily — web research / competitor discovery

**LLM providers** — five supported, with automatic fallback in priority order:
`mistral → qwen → openai → groq → anthropic` (first provider with a key set is used; a failed stream falls back to the next available provider). At least one of the five API keys must be set.

## Architecture

```
 User (browser)
      │
      ▼
 Next.js frontend  ──REST──▶  FastAPI backend
 (/build, /r/[token])         │
                               ├─▶ Research pipeline (BackgroundTask)
                               │     Tavily scrape/deep-dive → Playwright (Instagram)
                               │     → docs/{brand}/*.json → RAG index (embeddings + BM25)
                               │
                               ├─▶ ai_service.py  (agent prompt + RAG context)
                               │     → LLM (mistral/qwen/openai/groq/anthropic)
                               │     → markdown + ```recharts chart blocks
                               │
                               ├─▶ Report row (DB snapshot of generated content)
                               │
                               └─▶ Export services (deterministic, no LLM):
                                     export_service.py   → DOCX
                                     pptx_service.py      → PPTX
                                     pdf_service.py        → PDF (DOCX ──LibreOffice──▶ PDF)
                                     chart_renderer.py (matplotlib) + brand_theme.py
                                     shared by all three for identical charts/colors/logo
```

`backend/services/brand_theme.py` is the single source of truth for colors, logo placement, and bullet styling — both `export_service.py` (DOCX) and `pptx_service.py` (PPTX) import from it, which is why DOCX/PPTX/PDF all render the same brand look. `backend/utils/chart_renderer.py` is the equivalent shared module for chart rendering (matplotlib), mirroring the frontend's `ReportRenderer.tsx` chart-type logic (bar/line/area/radar/pie/scatter) so the same chart JSON produces a visually equivalent chart on-screen and in every export.

## Prerequisites

- **Node.js** — no version pinned in `package.json`; developed against Node 24. Next.js 16 requires a current Node LTS or newer.
- **Python** — no version pinned; developed against Python 3.14.
- **LibreOffice** — required for PDF export (`backend/services/pdf_service.py` shells out to `soffice`):
  - Windows: `winget install TheDocumentFoundation.LibreOffice`
  - Linux: `apt-get install --no-install-recommends libreoffice-writer libreoffice-core`
  - macOS: install LibreOffice.app normally (the service also checks `/Applications/LibreOffice.app/...` directly)
  - Override the resolved path with the `LIBREOFFICE_PATH` env var if `soffice`/`libreoffice` isn't on `PATH`.
- **Playwright Chromium** — required for the Instagram-scraping step of the research pipeline (`playwright install chromium`).

## Setup & Installation

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # macOS/Linux

pip install -r requirements.txt
playwright install chromium

# Create backend/.env — see Environment Variables below
cp .env.example .env             # then fill in real values

# Start the dev server (must be run with cwd = backend/, since main.py
# inserts the repo root into sys.path for its `from backend...` imports)
uvicorn main:app --reload --port 8000
```

The SQLite database (`backend/stratai.db`) ships in the repo already migrated. Alembic is present under `backend/alembic/` but its `env.py` is currently empty/unwired; schema changes beyond the base tables are instead applied as one-off scripts in `backend/scripts/` (safe to re-run — each skips its `ALTER TABLE` if the column already exists):

```bash
cd backend
python scripts/add_brand_kit.py
python scripts/add_competitor_details.py
python scripts/add_extracted_palette.py
```

### Frontend

```bash
cd frontend
npm install

# Create frontend/.env.local — see Environment Variables below

npm run dev
```

## Environment Variables

Names only — no values should ever be committed or echoed.

**Backend** (`backend/.env`)

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | Signs/verifies auth JWTs |
| `GOOGLE_CLIENT_ID` | Verifies Google Sign-In ID tokens (must match frontend's `NEXT_PUBLIC_GOOGLE_CLIENT_ID`) |
| `GOOGLE_CLIENT_SECRET` | Present for the same OAuth client; not currently read by any backend code |
| `ANTHROPIC_API_KEY` | LLM provider (fallback priority 5th) |
| `OPENAI_API_KEY` | LLM provider (fallback priority 3rd) |
| `MISTRAL_API_KEY` | LLM provider (fallback priority 1st) |
| `GROQ_API_KEY` | LLM provider (fallback priority 4th) |
| `QWEN_API_KEY` | LLM provider (fallback priority 2nd) |
| `ANTHROPIC_MODEL` / `OPENAI_MODEL` / `MISTRAL_MODEL` / `QWEN_MODEL` / `GROQ_MODEL` | Optional per-provider model overrides (each has a hardcoded default) |
| `TAVILY_API_KEY` | Required — web research / competitor discovery (brand scrape, deep dive, competitor search) |
| `FIRECRAWL_API_KEY` | Optional global fallback for the Firecrawl connector (per-user key takes precedence) |
| `EXA_API_KEY` | Optional global fallback for the Exa connector (per-user key takes precedence) |
| `CONNECTOR_ENCRYPTION_KEY` | Required for the Connectors feature — Fernet key encrypting stored per-user API keys. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `LIBREOFFICE_PATH` | Optional override for the `soffice`/`libreoffice` binary path (PDF export) |

**Frontend** (`frontend/.env.local`)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google Sign-In client ID (must match backend's `GOOGLE_CLIENT_ID`) |

## Running the App

| | Command | Default port |
|---|---|---|
| Backend | `cd backend && uvicorn main:app --reload --port 8000` | 8000 |
| Frontend | `cd frontend && npm run dev` | 3000 |

Frontend production build/start: `npm run build` then `npm start`.

## Export System

Exports are fully deterministic — no LLM call happens at export time. A report's markdown + ` ```recharts ` chart blocks (already generated and stored once, at report-creation time) are re-rendered into each format:

- **DOCX** (`export_service.py`) — parses the stored markdown (via `python-markdown`) and re-renders charts as matplotlib PNGs (`chart_renderer.py`) embedded inline.
- **PPTX** (`pptx_service.py`) — splits the same content into slides (with content-fit/line-budget logic to avoid overflow), embedding the same chart PNGs.
- **PDF** (`pdf_service.py`) — not rendered independently; it generates the DOCX first, then converts it to PDF via headless LibreOffice (`soffice --headless --convert-to pdf`), so the PDF always matches the DOCX exactly.

Brand theming is resolved in this priority order (`brand_theme.py`): an explicit **Brand Kit** (user-set logo + colors) → an **LLM-extracted color palette** from the brand's own site/assets → a built-in default theme per agent type.

## Project Structure

```
backend/
  main.py                    FastAPI app, CORS, static mount, router registration
  database.py                Async SQLAlchemy engine/session (SQLite)
  routers/                   auth, brand, projects, reports, report_sections, public, chat, agents, connectors
  services/
    ai_service.py              Agent prompts, RAG context, LLM provider selection/fallback, streaming
    blueprint_service.py       Loads report_blueprints.json, builds section-structure prompts
    pipeline_service.py        Background research pipeline (Tavily + Instagram scrape + RAG indexing)
    report_service.py          Report CRUD / snapshot persistence
    export_service.py          DOCX generation
    pptx_service.py             PPTX generation
    pdf_service.py               DOCX → PDF via LibreOffice
    brand_theme.py               Shared brand theme resolution (colors/logo) for DOCX+PPTX
    output_validator.py          Validates recharts JSON blocks (mirrors frontend's RechartsBlock logic)
    connector_service.py / encryption_service.py   Per-user connector credentials, encrypted at rest
    registry_service.py          Loads the agent catalog
    tavily_service.py / exa_service.py / firecrawl_service.py   Research providers
  utils/chart_renderer.py    Shared matplotlib chart rendering (bar/line/area/radar/pie/scatter)
  config/report_blueprints.json   Report section blueprints
  data/agents_registry.json        Agent catalog (31 agents, 6 categories)
  models/                     SQLAlchemy models (brand, connector, message, project, report, report_section, report_share, user)
  scripts/                    One-off SQLite column-migration scripts (Alembic isn't wired up)
  tests/                      pytest suite

frontend/
  src/app/                    Routes: / (landing), /auth, /brand-setup, /strategy-setup, /build (main app), /r/[token] (public share view)
  src/components/             Landing-page components (Hero, FeaturesGrid, Navbar, ...), ReportRenderer.tsx (markdown + chart rendering),
                              SectionEditor, BrandKitForm, CompetitorForm, ExportMenu
  src/components/builder/     The /build app UI: Sidebar, AgentsPanel, ChatInput, MainContent, ConnectorsPanel, FilesView, ...
  src/hooks/                  useAgents, useSections
  src/utils/pdfExport.ts      Client-side file-download helper (unrelated to the backend PDF export)
```

## Agents & Blueprints

The agent catalog lives in `backend/data/agents_registry.json` — 31 agents grouped into 6 categories, each with an `id`, `title`, `category`, `description`, optional `connectors`, and onboarding `questions`. `GET /api/agents` and `GET /api/agents/{agent_id}` serve this catalog to the frontend.

Each agent's system prompt is built in `ai_service.py` (`build_system_prompt`), then has a structured section outline appended from `blueprint_service.build_section_prompt()`, which reads `backend/config/report_blueprints.json`. That file has:
- `common_sections` — 5 sections every report includes (Executive Summary, Market Context, Consumer Landscape, Competitive Landscape, Key Insights)
- `agent_blueprints` — named, agent-specific section sets for 6 agent types (`brand-positioning`, `competition-analysis`, `seo-strategy`, `social-media-strategy`, `market-entry-strategy`, `content-calendar`)
- `default_blueprint` — a fallback section set used by the other 25 agents

**To add a new blueprint**: add an entry to `agent_blueprints` in `report_blueprints.json` keyed by the agent's hyphenated id, with `type_specific_sections` (each an `order`, `key`, `title`, optional `subsections`, and `content_guidance`). No code change is required — `build_section_prompt()` picks it up automatically.

## Notes / Known Requirements

- **LibreOffice must be installed on the production server** for PDF export to work — `pdf_service.py` resolves `soffice`/`libreoffice` from `LIBREOFFICE_PATH`, then `PATH`, then OS-specific default install locations, and raises a clear error if none are found (the PDF endpoint then returns HTTP 500 rather than failing silently).
- **License**: TBD — no `LICENSE` file is currently present in the repo.
- **Deployment target**: TBD — no Dockerfile or deployment config was found in the repo at the time of writing.
