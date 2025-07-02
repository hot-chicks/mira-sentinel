"""
Health check endpoints for Sentinel System.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
import subprocess
import os

from ..config import settings
from ..services.aider_service import AiderService
from ..services.git_service import GitService
from ..services.github_app_service import GitHubAppService

router = APIRouter()

class HealthStatus(BaseModel):
    """Health status response model."""
    status: str
    version: str
    checks: Dict[str, Any]


@router.get("", response_model=HealthStatus)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Checks:
    - Service status
    - GitHub API connectivity  
    - Claude Code CLI availability
    - Git configuration
    """
    checks = {}
    overall_status = "healthy"
    
    # Check GitHub authentication (App or Token)
    try:
        # Check if GitHub App is configured
        if settings.GITHUB_APP_ID and settings.GITHUB_APP_PRIVATE_KEY_PATH:
            github_app_service = GitHubAppService()
            app_health = await github_app_service.check_app_health()
            checks["github_auth"] = {
                "mode": "github_app",
                "status": "ok" if app_health["status"] == "healthy" else "error",
                **app_health
            }
            if app_health["status"] != "healthy":
                overall_status = "degraded"
        # Fallback to legacy token mode
        elif settings.GITHUB_TOKEN:
            checks["github_auth"] = {
                "mode": "personal_token",
                "status": "ok", 
                "configured": True,
                "note": "Using legacy PAT mode - consider migrating to GitHub App"
            }
        else:
            checks["github_auth"] = {
                "mode": "none",
                "status": "error", 
                "configured": False,
                "error": "Neither GitHub App nor Personal Access Token configured"
            }
            overall_status = "degraded"
    except Exception as e:
        checks["github_auth"] = {"status": "error", "error": str(e)}
        overall_status = "degraded"
    
    # Check Aider CLI availability
    try:
        aider_service = AiderService()
        aider_status = await aider_service.check_availability()
        
        if aider_status["available"]:
            checks["aider_cli"] = {
                "status": "ok",
                "available": True,
                "version": aider_status.get("version", "unknown"),
                "model": aider_status.get("model", "unknown"),
                "api_key_configured": aider_status.get("api_key_configured", False),
                "authenticated": aider_status.get("authenticated", False)
            }
        else:
            checks["aider_cli"] = {
                "status": "error",
                "available": False,
                "error": aider_status.get("error", "Unknown error")
            }
            overall_status = "degraded"
    except Exception as e:
        checks["aider_cli"] = {"status": "error", "available": False, "error": str(e)}
        overall_status = "degraded"
    
    # Check Git configuration
    try:
        git_service = GitService()
        git_config = await git_service.check_git_config()
        
        if git_config["configured"]:
            checks["git_config"] = {
                "status": "ok",
                "user_name": git_config.get("user_name"),
                "user_email": git_config.get("user_email"),
                "remote_origin": git_config.get("remote_origin"),
                "configured": True
            }
        else:
            checks["git_config"] = {
                "status": "incomplete",
                "configured": False,
                "error": "Git user name or email not configured"
            }
            overall_status = "degraded"
    except Exception as e:
        checks["git_config"] = {"status": "error", "error": str(e)}
        overall_status = "degraded"
    
    # Check repository access (depends on mode)
    try:
        if settings.GITHUB_APP_ID and settings.GITHUB_APP_PRIVATE_KEY_PATH:
            # GitHub App mode - show accessible repositories across all installations
            github_app_service = GitHubAppService()
            all_repo_info = await github_app_service.get_all_accessible_repositories()
            
            checks["repository_access"] = {
                "mode": "github_app",
                "status": "ok",
                "total_repositories": all_repo_info["total_repositories"],
                "unique_repositories": all_repo_info["unique_repositories"],
                "installations": all_repo_info["installations"],
                "sample_repositories": all_repo_info["all_repositories"][:10]  # Show first 10
            }
        elif settings.GITHUB_REPO:
            # Legacy single-repo mode
            checks["repository_access"] = {
                "mode": "single_repo",
                "status": "ok",
                "configured": True,
                "repo": settings.GITHUB_REPO,
                "note": "Legacy single-repo mode - consider migrating to GitHub App"
            }
        else:
            checks["repository_access"] = {
                "status": "error", 
                "configured": False,
                "error": "No repository access configured"
            }
            overall_status = "degraded"
    except Exception as e:
        checks["repository_access"] = {"status": "error", "error": str(e)}
        overall_status = "degraded"
    
    return HealthStatus(
        status=overall_status,
        version="0.1.0",
        checks=checks
    )


@router.get("/ready")
async def ready_check():
    """Simple readiness check for load balancers."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Simple liveness check for container orchestration."""
    return {"status": "alive"} 