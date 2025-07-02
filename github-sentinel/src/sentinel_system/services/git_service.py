"""
Git service for Sentinel System.

Handles all git operations including branch creation, commits, and pushes.
Works with workspace directories provided by WorkspaceService.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class GitService:
    """Service for handling git operations in workspace directories."""
    
    def __init__(self):
        """Initialize Git service."""
        pass
        
    async def _run_git_command(self, *args: str, repo_dir: Path, env: Optional[Dict[str, str]] = None) -> str:
        """
        Run a git command asynchronously in the specified directory.
        
        Args:
            *args: Git command arguments
            repo_dir: Repository directory path
            env: Environment variables
            
        Returns:
            Command output
        """
        try:
            cmd = ["git"] + list(args)
            logger.debug(f"Running git command: {' '.join(cmd)} in {repo_dir}")
            
            # Merge environment variables
            process_env = os.environ.copy()
            if env:
                process_env.update(env)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_dir,
                env=process_env
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown git error"
                logger.error(f"Git command failed: {error_msg}")
                raise Exception(f"Git command failed: {error_msg}")
            
            output = stdout.decode('utf-8').strip()
            logger.debug(f"Git command output: {output}")
            return output
            
        except Exception as e:
            logger.error(f"Error running git command: {str(e)}")
            raise
    
    async def get_current_branch(self, repo_dir: Path) -> str:
        """
        Get the current branch name.
        
        Args:
            repo_dir: Repository directory path
        
        Returns:
            Current branch name
        """
        try:
            output = await self._run_git_command("branch", "--show-current", repo_dir=repo_dir)
            return output.strip()
        except Exception as e:
            logger.error(f"Error getting current branch in {repo_dir}: {str(e)}")
            raise
    
    async def create_branch(self, branch_name: str, repo_dir: Path, from_branch: str = "main", env: Optional[Dict[str, str]] = None) -> None:
        """
        Create and checkout a new branch.
        
        Args:
            branch_name: Name of the new branch
            repo_dir: Repository directory path
            from_branch: Base branch to create from (default: main)
            env: Environment variables for git commands
        """
        try:
            logger.info(f"Creating branch '{branch_name}' from '{from_branch}' in {repo_dir}")
            
            # Check if there are uncommitted changes
            if await self.has_changes(repo_dir):
                logger.warning("Uncommitted changes detected, stashing them")
                await self._run_git_command("stash", "push", "-m", f"Auto-stash before creating branch {branch_name}", repo_dir=repo_dir, env=env)
            
            # Ensure we're on the base branch and it's up to date
            await self._run_git_command("checkout", from_branch, repo_dir=repo_dir, env=env)
            await self._run_git_command("pull", "origin", from_branch, repo_dir=repo_dir, env=env)
            
            # Create and checkout new branch
            await self._run_git_command("checkout", "-b", branch_name, repo_dir=repo_dir, env=env)
            
            logger.info(f"Successfully created and checked out branch '{branch_name}' in {repo_dir}")
            
        except Exception as e:
            logger.error(f"Error creating branch '{branch_name}' in {repo_dir}: {str(e)}")
            raise
    
    async def has_changes(self, repo_dir: Path) -> bool:
        """
        Check if there are any uncommitted changes.
        
        Args:
            repo_dir: Repository directory path
        
        Returns:
            True if there are changes, False otherwise
        """
        try:
            # Check for staged changes
            staged_output = await self._run_git_command("diff", "--cached", "--name-only", repo_dir=repo_dir)
            
            # Check for unstaged changes
            unstaged_output = await self._run_git_command("diff", "--name-only", repo_dir=repo_dir)
            
            # Check for untracked files
            untracked_output = await self._run_git_command("ls-files", "--others", "--exclude-standard", repo_dir=repo_dir)
            
            has_changes = bool(staged_output or unstaged_output or untracked_output)
            logger.debug(f"Repository {repo_dir} has changes: {has_changes}")
            
            return has_changes
            
        except Exception as e:
            logger.error(f"Error checking for changes in {repo_dir}: {str(e)}")
            raise
    
    async def add_all_changes(self, repo_dir: Path, env: Optional[Dict[str, str]] = None) -> None:
        """
        Add all changes to staging area.
        
        Args:
            repo_dir: Repository directory path
            env: Environment variables for git commands
        """
        try:
            await self._run_git_command("add", ".", repo_dir=repo_dir, env=env)
            logger.info(f"Added all changes to staging area in {repo_dir}")
        except Exception as e:
            logger.error(f"Error adding changes in {repo_dir}: {str(e)}")
            raise
    
    async def commit_changes(self, repo_dir: Path, message: str) -> bool:
        """
        Commit changes to the repository.
        
        Args:
            repo_dir: Repository directory path
            message: Commit message
            
        Returns:
            True if changes were committed, False otherwise
        """
        try:
            # Remove Aider history files before committing
            aider_files = [
                repo_dir / ".aider.chat.history.md",
                repo_dir / ".aider.input.history"
            ]
            
            for aider_file in aider_files:
                if aider_file.exists():
                    logger.info(f"Removing Aider history file: {aider_file}")
                    aider_file.unlink()
            
            # Check if there are any changes to commit
            status_output = await self._run_git_command("status", "--porcelain", repo_dir=repo_dir)
            
            if not status_output.strip():
                logger.info(f"No changes to commit in {repo_dir}")
                return False
            
            # Add all changes
            await self._run_git_command("add", ".", repo_dir=repo_dir)
            
            # Commit changes
            await self._run_git_command("commit", "-m", message, repo_dir=repo_dir)
            
            logger.info(f"Successfully committed changes in {repo_dir}: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error committing changes in {repo_dir}: {str(e)}")
            return False
    
    async def push_branch(self, branch_name: str, repo_dir: Path, remote: str = "origin", env: Optional[Dict[str, str]] = None) -> None:
        """
        Push branch to remote repository.
        
        Args:
            branch_name: Name of the branch to push
            repo_dir: Repository directory path
            remote: Remote name (default: origin)
            env: Environment variables for git commands
        """
        try:
            logger.info(f"Pushing branch '{branch_name}' to '{remote}' from {repo_dir}")
            
            # Push branch with upstream tracking
            await self._run_git_command("push", "-u", remote, branch_name, repo_dir=repo_dir, env=env)
            
            logger.info(f"Successfully pushed branch '{branch_name}' to '{remote}' from {repo_dir}")
            
        except Exception as e:
            logger.error(f"Error pushing branch '{branch_name}' from {repo_dir}: {str(e)}")
            raise
    
    async def get_changed_files(self, repo_dir: Path) -> List[str]:
        """
        Get list of changed files.
        
        Args:
            repo_dir: Repository directory path
        
        Returns:
            List of changed file paths
        """
        try:
            # Get staged files
            staged_files = await self._run_git_command("diff", "--cached", "--name-only", repo_dir=repo_dir)
            
            # Get unstaged files
            unstaged_files = await self._run_git_command("diff", "--name-only", repo_dir=repo_dir)
            
            # Get untracked files
            untracked_files = await self._run_git_command("ls-files", "--others", "--exclude-standard", repo_dir=repo_dir)
            
            all_files = []
            if staged_files:
                all_files.extend(staged_files.split('\n'))
            if unstaged_files:
                all_files.extend(unstaged_files.split('\n'))
            if untracked_files:
                all_files.extend(untracked_files.split('\n'))
            
            # Remove duplicates and empty strings
            changed_files = list(set(f for f in all_files if f))
            
            logger.debug(f"Changed files in {repo_dir}: {changed_files}")
            return changed_files
            
        except Exception as e:
            logger.error(f"Error getting changed files in {repo_dir}: {str(e)}")
            raise
    
    async def get_branch_status(self, repo_dir: Path) -> Dict[str, Any]:
        """
        Get detailed status of the current branch.
        
        Args:
            repo_dir: Repository directory path
        
        Returns:
            Status dictionary with branch information
        """
        try:
            current_branch = await self.get_current_branch(repo_dir)
            has_changes = await self.has_changes(repo_dir)
            changed_files = await self.get_changed_files(repo_dir)
            
            # Get last commit info
            try:
                last_commit = await self._run_git_command("log", "-1", "--pretty=format:%H|%an|%ad|%s", "--date=iso", repo_dir=repo_dir)
                commit_parts = last_commit.split('|', 3)
                last_commit_info = {
                    "hash": commit_parts[0] if len(commit_parts) > 0 else "",
                    "author": commit_parts[1] if len(commit_parts) > 1 else "",
                    "date": commit_parts[2] if len(commit_parts) > 2 else "",
                    "message": commit_parts[3] if len(commit_parts) > 3 else ""
                }
            except Exception:
                last_commit_info = None
            
            status = {
                "current_branch": current_branch,
                "has_changes": has_changes,
                "changed_files": changed_files,
                "changed_files_count": len(changed_files),
                "last_commit": last_commit_info,
                "repo_path": str(repo_dir)
            }
            
            logger.debug(f"Branch status in {repo_dir}: {status}")
            return status
            
        except Exception as e:
            logger.error(f"Error getting branch status in {repo_dir}: {str(e)}")
            raise
    
    async def cleanup_branch(self, branch_name: str, repo_dir: Path, remote: str = "origin", env: Optional[Dict[str, str]] = None) -> None:
        """
        Clean up a branch (checkout main and delete the branch).
        
        Args:
            branch_name: Name of the branch to clean up
            repo_dir: Repository directory path
            remote: Remote name (default: origin)
            env: Environment variables for git commands
        """
        try:
            logger.info(f"Cleaning up branch '{branch_name}' in {repo_dir}")
            
            # Checkout main branch
            await self._run_git_command("checkout", "main", repo_dir=repo_dir, env=env)
            
            # Delete local branch
            await self._run_git_command("branch", "-D", branch_name, repo_dir=repo_dir, env=env)
            
            # Delete remote branch (ignore errors if it doesn't exist)
            try:
                await self._run_git_command("push", remote, "--delete", branch_name, repo_dir=repo_dir, env=env)
            except Exception as e:
                logger.warning(f"Could not delete remote branch '{branch_name}' in {repo_dir}: {str(e)}")
            
            logger.info(f"Successfully cleaned up branch '{branch_name}' in {repo_dir}")
            
        except Exception as e:
            logger.error(f"Error cleaning up branch '{branch_name}' in {repo_dir}: {str(e)}")
            raise
    
    async def check_git_config(self, repo_dir: Path) -> Dict[str, Any]:
        """
        Check git configuration.
        
        Args:
            repo_dir: Repository directory path
        
        Returns:
            Git configuration status
        """
        try:
            config = {}
            
            # Check user name
            try:
                config["user_name"] = await self._run_git_command("config", "user.name", repo_dir=repo_dir)
            except Exception:
                config["user_name"] = None
            
            # Check user email
            try:
                config["user_email"] = await self._run_git_command("config", "user.email", repo_dir=repo_dir)
            except Exception:
                config["user_email"] = None
            
            # Check remote origin
            try:
                config["remote_origin"] = await self._run_git_command("config", "remote.origin.url", repo_dir=repo_dir)
            except Exception:
                config["remote_origin"] = None
            
            config["configured"] = bool(config["user_name"] and config["user_email"])
            config["repo_path"] = str(repo_dir)
            
            logger.debug(f"Git configuration in {repo_dir}: {config}")
            return config
            
        except Exception as e:
            logger.error(f"Error checking git config in {repo_dir}: {str(e)}")
            raise 