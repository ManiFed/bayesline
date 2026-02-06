"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.routes import router, set_orchestrator
from .services.orchestrator import Orchestrator

logger = structlog.get_logger()

orchestrator: Orchestrator | None = None
_background_task: asyncio.Task | None = None


async def _periodic_pipeline(orch: Orchestrator) -> None:
    """Background loop that runs the pipeline periodically."""
    while True:
        try:
            await orch.run_full_pipeline()
        except Exception:
            logger.error("periodic_pipeline.failed", exc_info=True)
        await asyncio.sleep(settings.market_poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator, _background_task

    logger.info("app.starting", app_name=settings.app_name)
    orchestrator = Orchestrator()
    set_orchestrator(orchestrator)

    # Run initial pipeline
    try:
        await orchestrator.run_full_pipeline()
    except Exception:
        logger.error("app.initial_pipeline_failed", exc_info=True)

    # Start background loop
    _background_task = asyncio.create_task(_periodic_pipeline(orchestrator))

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
    return {"status": "ok", "app": settings.app_name}
