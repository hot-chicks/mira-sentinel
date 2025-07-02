"""
Sentinel System - Autonomous GitHub Issue Resolution System

Main FastAPI application entry point.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import github, health, webhook

# Configure logging (console only)
log_level = os.environ.get("LOG_LEVEL", settings.LOG_LEVEL).upper()
numeric_log_level = getattr(logging, log_level, logging.INFO)

logging.basicConfig(
    level=numeric_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]  # Console output only
)

# Set log level for specific loggers
logging.getLogger("uvicorn").setLevel(numeric_log_level)
logging.getLogger("uvicorn.access").setLevel(numeric_log_level)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sentinel System",
    description="Autonomous GitHub issue resolution system using Claude Code CLI",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(github.router, prefix="/github", tags=["github"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])


@app.get("/")
async def root():
    """Root endpoint with basic system information."""
    logger.info("Root endpoint accessed.")
    return {
        "name": "Sentinel System",
        "version": "0.1.0",
        "description": "Autonomous GitHub issue resolution system",
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "disabled",
    }


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("🚀 Sentinel System starting up...")
    logger.info(f"📊 Debug mode: {settings.DEBUG}")
    
    # Show GitHub configuration
    if hasattr(settings, 'GITHUB_APP_ID') and settings.GITHUB_APP_ID:
        logger.info(f"🎯 GitHub App ID: {settings.GITHUB_APP_ID}")
        if hasattr(settings, 'GITHUB_APP_INSTALLATION_IDS') and settings.GITHUB_APP_INSTALLATION_IDS:
            installation_count = len(settings.GITHUB_APP_INSTALLATION_IDS.split(','))
            logger.info(f"📦 Multi-installation mode: {installation_count} installations configured")
        else:
            logger.info("📦 Single installation mode")
    else:
        logger.info("🎯 Legacy PAT mode")
    
    logger.info(f"🏷️  Issue label: '{settings.GITHUB_ISSUE_LABEL}'")
    logger.info(f"📁 Workspace directory: {settings.WORKSPACE_BASE_DIR}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("🛑 Sentinel System shutting down...") 