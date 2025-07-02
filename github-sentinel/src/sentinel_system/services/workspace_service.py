"""
Workspace service for Sentinel System.

Handles repository cloning, workspace management, and cleanup for multi-repository operations.
Designed for Docker container environments with ephemeral workspaces.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from ..config import settings
from .github_service import GitHubService

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Service for managing repository workspaces in Docker environment."""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.base_workspace_dir = Path(settings.WORKSPACE_BASE_DIR if hasattr(settings, 'WORKSPACE_BASE_DIR') else "/tmp/sentinel-workspaces")
        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"WorkspaceService initialized with base directory: {self.base_workspace_dir}")
    
    async def _run_command(self, command: list, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> str:
        """
        Run a command asynchronously.
        
        Args:
            command: Command and arguments as list
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Command output
        """
        try:
            logger.debug(f"Running command: {' '.join(command)} in {cwd or 'current dir'}")
            
            # Merge environment variables
            process_env = os.environ.copy()
            if env:
                process_env.update(env)
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=process_env
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown command error"
                logger.error(f"Command failed: {error_msg}")
                raise Exception(f"Command failed: {error_msg}")
            
            output = stdout.decode('utf-8').strip()
            logger.debug(f"Command output: {output}")
            return output
            
        except Exception as e:
            logger.error(f"Error running command {' '.join(command)}: {str(e)}")
            raise
    
    async def clone_repository(self, repository: str, workspace_dir: Path) -> Path:
        """
        Clone a repository to the workspace directory.
        
        Args:
            repository: Repository full name (owner/repo)
            workspace_dir: Workspace directory path
            
        Returns:
            Path to cloned repository
        """
        try:
            logger.info(f"Cloning repository {repository} to {workspace_dir}")
            
            # Get clone URL and authentication
            clone_url = self.github_service.get_clone_url(repository)
            repo_dir = workspace_dir / repository.replace('/', '_')
            
            # Ensure the target directory doesn't exist
            if repo_dir.exists():
                logger.warning(f"Repository directory {repo_dir} already exists, cleaning up")
                shutil.rmtree(repo_dir, ignore_errors=True)
            
            # Prepare git environment with authentication
            git_env = {}
            
            # Get installation token for GitHub App authentication
            if self.github_service.mode == "github_app":
                token = await self.github_service.get_repository_token(repository)
                if token:
                    # Use token authentication for HTTPS clone
                    auth_clone_url = clone_url.replace('https://', f'https://x-access-token:{token}@')
                    clone_url = auth_clone_url
            elif self.github_service.mode == "legacy" and hasattr(settings, 'GITHUB_TOKEN'):
                # Use PAT for legacy mode
                auth_clone_url = clone_url.replace('https://', f'https://{settings.GITHUB_TOKEN}@')
                clone_url = auth_clone_url
            
            # Clone the repository with better error handling
            try:
                await self._run_command([
                    "git", "clone", "--depth", "1", clone_url, str(repo_dir)
                ], env=git_env)
            except Exception as clone_error:
                logger.error(f"Git clone failed: {str(clone_error)}")
                # Clean up partial clone if it exists
                if repo_dir.exists():
                    shutil.rmtree(repo_dir, ignore_errors=True)
                raise Exception(f"Failed to clone repository: {str(clone_error)}")
            
            # Verify the repository was cloned successfully
            if not repo_dir.exists():
                raise Exception(f"Repository directory {repo_dir} was not created")
            
            git_dir = repo_dir / ".git"
            if not git_dir.exists():
                raise Exception(f"Git directory {git_dir} was not created")
            
            # Wait a moment for filesystem to settle
            await asyncio.sleep(0.1)
            
            # Configure git user for commits with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self._run_command([
                        "git", "config", "user.name", "Sentinel System"
                    ], cwd=repo_dir)
                    
                    await self._run_command([
                        "git", "config", "user.email", "sentinel@github-app.local"
                    ], cwd=repo_dir)
                    
                    # If we get here, configuration succeeded
                    break
                    
                except Exception as config_error:
                    if attempt < max_retries - 1:
                        logger.warning(f"Git config attempt {attempt + 1} failed, retrying: {str(config_error)}")
                        await asyncio.sleep(0.5)  # Wait before retry
                    else:
                        logger.error(f"Git config failed after {max_retries} attempts: {str(config_error)}")
                        # Don't fail the entire operation for config issues
                        logger.warning("Continuing without git user configuration")
            
            logger.info(f"Successfully cloned {repository} to {repo_dir}")
            return repo_dir
            
        except Exception as e:
            logger.error(f"Error cloning repository {repository}: {str(e)}")
            raise
    
    async def create_workspace(self, repository: str, issue_number: int) -> Path:
        """
        Create a workspace directory for a repository and issue.
        
        Args:
            repository: Repository full name (owner/repo)
            issue_number: Issue number
            
        Returns:
            Path to workspace directory
        """
        try:
            # Create unique workspace directory
            workspace_name = f"{repository.replace('/', '_')}_issue_{issue_number}_{os.getpid()}"
            workspace_dir = self.base_workspace_dir / workspace_name
            
            # Clean up if directory already exists
            if workspace_dir.exists():
                logger.warning(f"Workspace {workspace_dir} already exists, cleaning up")
                shutil.rmtree(workspace_dir, ignore_errors=True)
            
            # Create directory with proper permissions
            workspace_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Ensure the directory is writable
            if not os.access(workspace_dir, os.W_OK):
                logger.warning(f"Workspace {workspace_dir} is not writable, attempting to fix permissions")
                os.chmod(workspace_dir, 0o755)
            
            logger.info(f"Created workspace directory: {workspace_dir}")
            
            return workspace_dir
            
        except Exception as e:
            logger.error(f"Error creating workspace for {repository} issue #{issue_number}: {str(e)}")
            raise
    
    async def cleanup_workspace(self, workspace_dir: Path) -> None:
        """
        Clean up a workspace directory.
        
        Args:
            workspace_dir: Workspace directory to clean up
        """
        try:
            if workspace_dir.exists():
                logger.info(f"Cleaning up workspace: {workspace_dir}")
                shutil.rmtree(workspace_dir, ignore_errors=True)
                logger.info(f"Successfully cleaned up workspace: {workspace_dir}")
            else:
                logger.debug(f"Workspace {workspace_dir} does not exist, nothing to clean up")
                
        except Exception as e:
            logger.error(f"Error cleaning up workspace {workspace_dir}: {str(e)}")
            # Don't raise exception for cleanup errors - log and continue
    
    @asynccontextmanager
    async def repository_workspace(self, repository: str, issue_number: int):
        """
        Context manager for repository workspace with automatic cleanup.
        
        Args:
            repository: Repository full name (owner/repo)
            issue_number: Issue number
            
        Yields:
            Path to the cloned repository directory
        """
        workspace_dir = None
        repo_dir = None
        
        try:
            # Create workspace
            workspace_dir = await self.create_workspace(repository, issue_number)
            
            # Clone repository
            repo_dir = await self.clone_repository(repository, workspace_dir)
            
            logger.info(f"Repository workspace ready: {repo_dir}")
            yield repo_dir
            
        except Exception as e:
            logger.error(f"Error in repository workspace for {repository} issue #{issue_number}: {str(e)}")
            raise
        finally:
            # Always cleanup workspace
            if workspace_dir:
                await self.cleanup_workspace(workspace_dir)
    
    async def get_workspace_info(self, repo_dir: Path) -> Dict[str, Any]:
        """
        Get information about the current workspace.
        
        Args:
            repo_dir: Repository directory path
            
        Returns:
            Workspace information dictionary
        """
        try:
            info = {
                "repo_dir": str(repo_dir),
                "exists": repo_dir.exists(),
                "is_git_repo": False,
                "current_branch": None,
                "has_changes": False,
                "files_count": 0
            }
            
            if repo_dir.exists():
                # Check if it's a git repository
                git_dir = repo_dir / ".git"
                info["is_git_repo"] = git_dir.exists()
                
                if info["is_git_repo"]:
                    # Get current branch
                    try:
                        branch_output = await self._run_command(
                            ["git", "branch", "--show-current"], 
                            cwd=repo_dir
                        )
                        info["current_branch"] = branch_output.strip()
                    except Exception:
                        pass
                    
                    # Check for changes
                    try:
                        status_output = await self._run_command(
                            ["git", "status", "--porcelain"], 
                            cwd=repo_dir
                        )
                        info["has_changes"] = bool(status_output.strip())
                    except Exception:
                        pass
                
                # Count files
                try:
                    info["files_count"] = len(list(repo_dir.rglob("*")))
                except Exception:
                    pass
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting workspace info for {repo_dir}: {str(e)}")
            return {"error": str(e)}
    
    async def prepare_git_environment(self, repo_dir: Path, repository: str) -> Dict[str, str]:
        """
        Prepare git environment variables for authenticated operations.
        
        Args:
            repo_dir: Repository directory path
            repository: Repository full name (owner/repo)
            
        Returns:
            Environment variables dictionary
        """
        try:
            git_env = {}
            
            # Set up authentication based on mode
            if self.github_service.mode == "github_app":
                token = await self.github_service.get_repository_token(repository)
                if token:
                    # Configure git to use token authentication
                    git_env["GIT_ASKPASS"] = "echo"
                    git_env["GIT_USERNAME"] = "x-access-token"
                    git_env["GIT_PASSWORD"] = token
                    
                    # Configure remote URL with token
                    remote_url = f"https://x-access-token:{token}@github.com/{repository}.git"
                    await self._run_command([
                        "git", "remote", "set-url", "origin", remote_url
                    ], cwd=repo_dir)
                    
            elif self.github_service.mode == "legacy" and hasattr(settings, 'GITHUB_TOKEN'):
                # Use PAT for legacy mode
                git_env["GIT_ASKPASS"] = "echo"
                git_env["GIT_USERNAME"] = settings.GITHUB_TOKEN
                git_env["GIT_PASSWORD"] = ""
                
                # Configure remote URL with PAT
                remote_url = f"https://{settings.GITHUB_TOKEN}@github.com/{repository}.git"
                await self._run_command([
                    "git", "remote", "set-url", "origin", remote_url
                ], cwd=repo_dir)
            
            logger.debug(f"Prepared git environment for {repository}")
            return git_env
            
        except Exception as e:
            logger.error(f"Error preparing git environment for {repository}: {str(e)}")
            return {} 