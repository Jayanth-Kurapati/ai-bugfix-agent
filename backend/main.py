"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from backend.api.jobs import JobStore
from backend.api.routes import router as api_router
from backend.agent.llm_client import OpenRouterClient

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.job_store = JobStore()
    app.state.llm_client = OpenRouterClient()
    app.state.model_discovery = app.state.llm_client.discover_models()
    yield


app = FastAPI(title="AI Bug-Fixing Agent", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Minimal process readiness endpoint for the backend foundation."""

    return {"status": "ok"}


# Serve the Vite production build as static files.
# Mounted last so /api and /health take priority.
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
