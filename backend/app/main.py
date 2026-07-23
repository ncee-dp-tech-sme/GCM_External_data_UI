"""
2026-06-01T23:17:00Z - Added static file serving for frontend UI
2026-07-25T00:00:00Z - Wire settings.log_level into Python logging on startup
2026-07-25T00:00:00Z - Call migrate_db() on startup to add new columns to existing tables
Main FastAPI application
Entry point for the GCM Web UI backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import os

from app.config import settings
from app.database import init_db, migrate_db
from app.api import api_router

# Apply log level from settings immediately at import time so all loggers
# (including those in services) respect the configured level.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Runs on startup and shutdown
    """
    # Startup: Initialize database and apply column migrations
    print("Initializing database...")
    init_db()
    migrate_db()
    print("Database initialized successfully")
    
    yield
    
    # Shutdown: Cleanup if needed
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Web UI for Guardium Cryptography Manager API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Get the frontend directory path
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

# Mount static files (CSS, JS)
if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")


@app.get("/")
async def root():
    """Serve the main UI page"""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        # Fallback to API information if frontend not found
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/api/docs",
            "note": "Frontend UI not found. Please ensure frontend files are in the correct location."
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

# Made with Bob
