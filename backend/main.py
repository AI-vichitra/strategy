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

# Manually load .env since dotenv package is conflicting
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key] = val

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import auth, brand, projects, chat, agents, connectors, reports, public

app = FastAPI(title="StratAI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(brand.router, prefix="/api/brands", tags=["Brands"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(public.router, prefix="/api/public", tags=["Public"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(agents.router)
app.include_router(connectors.router)

@app.get("/")
async def root():
    return {"message": "StratAI API is running"}
