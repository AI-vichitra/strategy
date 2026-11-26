import os
import sys
import asyncio

# Ensure root directory is in sys.path so 'backend...' imports work when running inside backend/
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# On Windows, set ProactorEventLoopPolicy so background tasks can spawn subprocesses cleanly
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# Load .env into os.environ — no-op when the file is absent (cloud hosts supply vars directly).
# Real environment wins: a key already set in the environment is NOT overwritten by .env.
# (The previous code overwrote unconditionally, giving .env higher precedence than the shell
# environment, which is the reverse of what cloud platforms expect.)
env_path = os.path.join(os.path.dirname(__file__), '.env')
try:
    with open(env_path, 'r') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _val = _line.split('=', 1)
                _key = _key.strip()
                if _key and _key not in os.environ:
                    os.environ[_key] = _val.strip()
except (FileNotFoundError, PermissionError):
    pass  # No .env on this host — that is fine

import logging

# Without this, the root logger stays at its Python default (WARNING) with no
# handler of its own — every `logger.info(...)` call across the app (pipeline
# progress, report-gating decisions, etc.) is silently dropped before it ever
# reaches a handler, even under uvicorn: uvicorn's default log config only
# attaches a handler to its own "uvicorn"/"uvicorn.access" loggers, not root.
# LOG_LEVEL lets ops raise/lower verbosity without a code change.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

logger = logging.getLogger(__name__)

from backend.routers import auth, brand, projects, chat, agents, connectors, reports, public, report_sections, pptx_templates, tasks
from backend.database import engine, Base

# Import every model so Base.metadata is fully populated before create_all runs.
# models/__init__.py re-exports all 8 mapped classes:
#   User, BrandConfig, Project, Message, Report, ReportShare, ReportSection, ConnectorCredential
# That covers all 8 application tables (alembic_version is managed by alembic tooling, not create_all).
import backend.models  # noqa: F401 — registers all ORM classes with Base.metadata

app = FastAPI(title="StratAI Backend")

# ── Startup: ensure schema exists on a fresh database ────────────────────────
@app.on_event("startup")
async def _create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _add_missing_columns()

# Alembic isn't wired up in this project (see models/ — create_all() is the
# only migration mechanism), so create_all() only creates missing TABLES. A
# new column added to an existing model needs an explicit ALTER TABLE here.
# Each statement runs in its own transaction and swallows the "column already
# exists" error, so this is idempotent — a fresh DB (where create_all() just
# created the column) hits the same harmless no-op as a redeploy.
_NEW_COLUMNS = [
    # (table, column, postgres_type, sqlite_type)
    ("brand_configs", "kb_json", "TEXT", "TEXT"),
    ("projects", "logo_data", "BYTEA", "BLOB"),
    ("projects", "logo_mime", "VARCHAR(100)", "TEXT"),
    ("brand_configs", "target_market", "TEXT", "TEXT"),
    ("brand_configs", "additional_notes", "TEXT", "TEXT"),
    ("brand_configs", "social_handles", "TEXT", "TEXT"),
    ("brand_configs", "brand_brief", "TEXT", "TEXT"),
    ("reports", "truncation_info", "TEXT", "TEXT"),
    ("projects", "research_json", "TEXT", "TEXT"),
]


async def _add_missing_columns():
    is_sqlite = engine.dialect.name == "sqlite"
    for table, column, pg_type, sqlite_type in _NEW_COLUMNS:
        col_type = sqlite_type if is_sqlite else pg_type
        stmt = (
            f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            if is_sqlite
            else f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"
        )
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception as e:
            logger.info(f"[startup] Skipping '{table}.{column}' column add (likely already exists): {e}")

# ── CORS ──────────────────────────────────────────────────────────────────────
# CORS_ORIGINS: comma-separated list of allowed origins.  Defaults to localhost
# for local dev.  Vercel preview URLs are covered by allow_origin_regex.
_raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
_allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(_static_dir, "uploads", "logos"), exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(brand.router, prefix="/api/brands", tags=["Brands"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(report_sections.router, prefix="/api/reports", tags=["Report Sections"])
app.include_router(public.router, prefix="/api/public", tags=["Public"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(agents.router)
app.include_router(pptx_templates.router)
app.include_router(connectors.router)
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])

@app.get("/")
async def root():
    return {"message": "StratAI API is running"}
