"""
Configuration settings for Sentinel System.

Uses Pydantic Settings for environment-based configuration.
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    DEBUG: bool = True
    
    GITHUB_WEBHOOK_SECRET: str = Field(
        default="",
        description="GitHub webhook secret for signature verification (optional)"
    )
    
    # GitHub App settings (New multi-repo mode)
    GITHUB_APP_ID: str = Field(default="", description="GitHub App ID")
    GITHUB_APP_PRIVATE_KEY_PATH: str = Field(
        default="", 
        description="Path to GitHub App private key file"
    )
    GITHUB_APP_INSTALLATION_IDS: str = Field(
        default="", 
        description="Comma-separated list of GitHub App installation IDs for multi-organization support"
    )
    
    # Anthropic API Configuration for Aider
    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Anthropic API key for Aider LLM integration"
    )
    
    # GitHub Labels (hardcoded - no need to configure)
    GITHUB_ISSUE_LABEL: str = "sentinel-analyze"
    GITHUB_PROPOSAL_LABEL: str = "proposal-pending"
    GITHUB_APPROVED_LABEL: str = "approved"
    GITHUB_WORKING_LABEL: str = "implementing"
    
    # Git Settings (hardcoded - no need to configure)
    GIT_BRANCH_PREFIX: str = "sentinel/issue-"
    GIT_COMMIT_PREFIX: str = "feat: "
    
    # Workspace Settings (hardcoded - no need to configure)
    WORKSPACE_BASE_DIR: str = "/tmp/sentinel-workspaces"
    
    LOG_LEVEL: str = "INFO"
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields for backward compatibility


# Global settings instance
settings = Settings()
