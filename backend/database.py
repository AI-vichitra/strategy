import os
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SQLITE_FALLBACK = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'stratai.db')}"


def _resolve_database_url():
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        return _SQLITE_FALLBACK, {"check_same_thread": False}

    # Neon / Heroku supply postgres:// or postgresql:// — asyncpg needs postgresql+asyncpg://
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]

    # asyncpg rejects ?sslmode=require as a query param — strip it; pass ssl via connect_args
    raw = re.sub(r"[?&]sslmode=[^&]*", "", raw).rstrip("?&")

    return raw, {"ssl": True}


SQLALCHEMY_DATABASE_URL, _connect_args = _resolve_database_url()

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    # echo=True  # Useful for debugging SQL queries
)

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

# Alias used by pipeline_service as a session factory
async_session = SessionLocal
