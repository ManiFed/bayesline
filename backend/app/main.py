"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .api.routes import router, set_orchestrator
from .services.orchestrator import Orchestrator

logger = structlog.get_logger()

orchestrator: Orchestrator | None = None
_background_task: asyncio.Task | None = None


async def _periodic_pipeline(orch: Orchestrator) -> None:
    """Background loop that runs the pipeline periodically.

    The first run starts after a short delay so the server can pass health
    checks immediately after startup.
    """
    await asyncio.sleep(2)
    while True:
        try:
            await asyncio.wait_for(
                orch.run_full_pipeline(),
                timeout=float(settings.market_poll_interval),
            )
        except asyncio.TimeoutError:
            logger.error("periodic_pipeline.timeout")
        except Exception:
            logger.error("periodic_pipeline.failed", exc_info=True)
        await asyncio.sleep(settings.market_poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, _background_task

    logger.info("app.starting", app_name=settings.app_name)
    orchestrator = Orchestrator()
    set_orchestrator(orchestrator)

    # Start the pipeline in the background — do NOT block startup.
    # This lets the server start accepting requests (and pass health checks)
    # immediately, even if external APIs are slow or unreachable.
    _background_task = asyncio.create_task(_periodic_pipeline(orchestrator))
    logger.info("app.ready", msg="Accepting requests; pipeline running in background")

    yield

    # Shutdown
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass
    if orchestrator:
        await orchestrator.close()
    logger.info("app.shutdown")


app = FastAPI(
    title="Bayesline",
    description="News discovery platform powered by informed attention signals",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Liveness probe — always returns 200 once the process is up."""
    return {"status": "ok", "app": settings.app_name}


@app.get("/ready")
async def readiness():
    """Readiness probe — returns 200 only after the first pipeline run."""
    if orchestrator and orchestrator.store.stats()["topics"] > 0:
        return {"status": "ready", "topics": orchestrator.store.stats()["topics"]}
    return {"status": "warming_up", "topics": 0}


# Serve the built frontend LAST — mount("/") is a catch-all that will shadow
# any route registered after it.  By placing it here, /health, /ready, and
# /api/v1/* are all registered first and take priority.
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
