"""
Agentic AI Research Platform — FastAPI Application.

Entry point: python main.py
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path to resolve local imports cleanly
sys.path.append(str(Path(__file__).resolve().parent))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.api.auth import router as auth_router
from app.api.research import router as research_router
from app.api.agents import router as agents_router
from app.api.reports import router as reports_router
from app.api.settings import router as settings_router
from app.api.logs import router as logs_router
from app.api.websocket import manager as ws_manager
from app.schemas.common import HealthResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("═" * 60)
    logger.info("  🧠 Agentic AI Research Platform")
    logger.info("  Starting up...")
    logger.info("═" * 60)

    # Initialize database tables
    await init_db()
    logger.info("✓ Database initialized")
    logger.info(f"✓ Server ready at http://{settings.HOST}:{settings.PORT}")

    yield

    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Agentic AI Research Platform",
        description="Multi-agent AI research platform with iterative feedback loops",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(research_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(logs_router, prefix="/api/v1")

    # Health check
    @app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        return HealthResponse(timestamp=datetime.now(timezone.utc))

    # WebSocket endpoint
    @app.websocket("/ws/research/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str):
        await ws_manager.connect(session_id, websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # Client can send ping/pong
        except WebSocketDisconnect:
            ws_manager.disconnect(session_id, websocket)

    # Serve frontend static files
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")
        app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
        app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the SPA frontend for all non-API routes."""
            file_path = frontend_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(frontend_dir / "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
