from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers.data import router as data_router
from app.routers.ingest import router as ingest_router
from app.routers.proficy import router as proficy_router
from app.routers.query import router as query_router
from app.services.scheduler import NightlyIngestionScheduler


settings = get_settings()
init_db(settings.db_path)
scheduler = NightlyIngestionScheduler(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(
    title="MCM5 AI Maintenance Assistant",
    version="0.1.0",
    description="Backend inicial para ingesta y consulta del historico de mantenimiento MCM5.",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return RedirectResponse(url="/ui")


@app.get("/health")
def health():
    return {
        "name": "MCM5 AI Maintenance Assistant",
        "version": "0.1.0",
        "docs": "/docs",
        "db_path": str(settings.db_path),
    }


@app.get("/ui")
def ui():
    return FileResponse(settings.static_dir / "index.html")


app.include_router(ingest_router)
app.include_router(data_router)
app.include_router(query_router)
app.include_router(proficy_router)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
