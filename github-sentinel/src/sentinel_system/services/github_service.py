"""
GitHub API service for Sentinel System.

Handles all GitHub API operations including issues, labels, comments, and repository management.
Supports both GitHub App (multi-repo) and legacy Personal Access Token (single-repo) modes.
"""

import httpx
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..config import settings
from .github_app_service import GitHubAppService

logger = logging.getLogger(__name__)


class GitHubService:
    """Service for interacting with GitHub API with multi-repository support."""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.github_app_service = None
        
        # Initialize GitHub App service if configured
        if settings.GITHUB_APP_ID and settings.GITHUB_APP_PRIVATE_KEY_PATH:
            self.github_app_service = GitHubAppService()
            self.mode = "github_app"
            logger.info("GitHubService initialized in GitHub App mode")
        elif settings.GITHUB_TOKEN and settings.GITHUB_REPO:
            self.mode = "legacy"
            self.legacy_repo = settings.GITHUB_REPO
            self.legacy_headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Sentinel-System/0.1.0"
            }
            logger.info("GitHubService initialized in legacy PAT mode")
        else:
            raise Exception("GitHub authentication not configured. Set either GitHub App or PAT credentials.")
    
    async def _get_authenticated_client(self, repository: Optional[str] = None) -> httpx.AsyncClient:
        """
        Get an authenticated HTTP client for GitHub API calls.
        
        Args:
            repository: Repository full name (owner/repo) - required for GitHub App mode
            
        Returns:
            Authenticated HTTP client
        """
        if self.mode == "github_app":
            if not self.github_app_service:
                raise Exception("GitHub App service not initialized")
            
            # Find the correct installation for this repository
            if repository:
                installation_id = await self.github_app_service.find_installation_for_repository(repository)
                if installation_id is None:
                    raise Exception(f"Repository {repository} not accessible via any GitHub App installation")
                return await self.github_app_service.get_authenticated_client(installation_id)
            else:
                # Fallback to default installation if no repository specified
                return await self.github_app_service.get_authenticated_client()
        else:
            # Legacy PAT mode
            return httpx.AsyncClient(headers=self.legacy_headers)
    
    def _get_repo_for_request(self, repository: Optional[str] = None) -> str:
        """
        Get the repository name for API requests.
        
        Args:
            repository: Repository full name (owner/repo)
            
        Returns:
            Repository name to use in API calls
        """
        if self.mode == "github_app":
            if not repository:
                raise Exception("Repository parameter required in GitHub App mode")
            return repository
        else:
            # Legacy mode - use configured repo, ignore repository parameter
            return self.legacy_repo
    
    async def get_issues(
        self, 
        repository: Optional[str] = None,
        label: Optional[str] = None, 
        state: str = "open", 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get issues from the repository.
        
        Args:
            repository: Repository full name (owner/repo) - required for GitHub App mode
            label: Filter by label
            state: Issue state (open, closed, all)
            limit: Maximum number of issues to return
            
        Returns:
            List of issue dictionaries
        """
        try:
            repo = self._get_repo_for_request(repository)
            
            params = {
                "state": state,
                "per_page": min(limit, 100),  # GitHub API limit
                "sort": "created",
                "direction": "desc"
            }
            
            if label:
                params["labels"] = label
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{repo}/issues",
                    params=params
                )
                response.raise_for_status()
                
                issues = response.json()
                logger.info(f"Retrieved {len(issues)} issues from {repo}")
                return issues
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching issues from {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def get_issue(self, issue_number: int, repository: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a specific issue by number.
        
        Args:
            issue_number: Issue number
            repository: Repository full name (owner/repo) - required for GitHub App mode
            
        Returns:
            Issue dictionary
        """
        try:
            repo = self._get_repo_for_request(repository)
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{repo}/issues/{issue_number}"
                )
                response.raise_for_status()
                
                issue = response.json()
                logger.info(f"Retrieved issue #{issue_number} from {repo}")
                return issue
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching issue #{issue_number} from {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def add_comment(self, issue_number: int, comment: str, repository: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a comment to an issue.
        
        Args:
            issue_number: Issue number
            comment: Comment text
            repository: Repository full name (owner/repo) - required for GitHub App mode
            
        Returns:
            Comment dictionary
        """
        try:
            repo = self._get_repo_for_request(repository)
            data = {"body": comment}
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments",
                    json=data
                )
                response.raise_for_status()
                
                comment_data = response.json()
                logger.info(f"Added comment to issue #{issue_number} in {repo}")
                return comment_data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error adding comment to issue #{issue_number} in {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def add_label(self, issue_number: int, label: str, repository: Optional[str] = None) -> None:
        """
        Add a label to an issue.
        
        Args:
            issue_number: Issue number
            label: Label name
            repository: Repository full name (owner/repo) - required for GitHub App mode
        """
        try:
            repo = self._get_repo_for_request(repository)
            data = {"labels": [label]}
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{repo}/issues/{issue_number}/labels",
                    json=data
                )
                response.raise_for_status()
                
                logger.info(f"Added label '{label}' to issue #{issue_number} in {repo}")
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error adding label to issue #{issue_number} in {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def remove_label(self, issue_number: int, label: str, repository: Optional[str] = None) -> None:
        """
        Remove a label from an issue.
        
        Args:
            issue_number: Issue number
            label: Label name
            repository: Repository full name (owner/repo) - required for GitHub App mode
        """
        try:
            repo = self._get_repo_for_request(repository)
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.delete(
                    f"{self.base_url}/repos/{repo}/issues/{issue_number}/labels/{label}"
                )
                # 404 is acceptable - label might not exist
                if response.status_code not in [200, 204, 404]:
                    response.raise_for_status()
                
                logger.info(f"Removed label '{label}' from issue #{issue_number} in {repo}")
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:  # Ignore 404 for non-existent labels
                logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
                raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error removing label from issue #{issue_number} in {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def get_labels(self, repository: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all labels from the repository.
        
        Args:
            repository: Repository full name (owner/repo) - required for GitHub App mode
            
        Returns:
            List of label dictionaries
        """
        try:
            repo = self._get_repo_for_request(repository)
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{repo}/labels"
                )
                response.raise_for_status()
                
                labels = response.json()
                logger.info(f"Retrieved {len(labels)} labels from {repo}")
                return labels
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching labels from {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        repository: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch (default: main)
            repository: Repository full name (owner/repo) - required for GitHub App mode
            
        Returns:
            Pull request dictionary
        """
        try:
            repo = self._get_repo_for_request(repository)
            data = {
                "title": title,
                "body": body,
                "head": head,
                "base": base
            }
            
            async with await self._get_authenticated_client(repository) as client:
                response = await client.post(
                    f"{self.base_url}/repos/{repo}/pulls",
                    json=data
                )
                response.raise_for_status()
                
                pr_data = response.json()
                logger.info(f"Created pull request in {repo}: {pr_data['html_url']}")
                return pr_data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error creating pull request in {repository or 'configured repo'}: {str(e)}")
            raise
    
    async def get_repository_info(self, repository: str) -> Dict[str, Any]:
        """
        Get repository information.
        
        Args:
            repository: Repository full name (owner/repo)
            
        Returns:
            Repository information dictionary
        """
        try:
            async with await self._get_authenticated_client(repository) as client:
                response = await client.get(
                    f"{self.base_url}/repos/{repository}"
                )
                response.raise_for_status()
                
                repo_data = response.json()
                logger.info(f"Retrieved repository info for {repository}")
                return repo_data
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching repository info for {repository}: {str(e)}")
            raise
    
    def get_clone_url(self, repository: str) -> str:
        """
        Get the clone URL for a repository.
        
        Args:
            repository: Repository full name (owner/repo)
            
        Returns:
            Git clone URL
        """
        if self.mode == "github_app":
            # For GitHub App, we'll use HTTPS with token authentication
            return f"https://github.com/{repository}.git"
        else:
            # Legacy mode - use configured repository
            return f"https://github.com/{self.legacy_repo}.git"
    
    async def get_installation_token(self) -> Optional[str]:
        """
        Get GitHub App installation token (for git operations).
        
        Returns:
            Installation token if in GitHub App mode, None otherwise
        """
        if self.mode == "github_app" and self.github_app_service:
            return await self.github_app_service.get_installation_token()
        return None
    
    async def get_repository_token(self, repository: str) -> Optional[str]:
        """
        Get GitHub App installation token for a specific repository.
        
        Args:
            repository: Repository full name (owner/repo)
            
        Returns:
            Installation token for the repository if in GitHub App mode, None otherwise
        """
        if self.mode == "github_app" and self.github_app_service:
            # Find the correct installation for this repository
            installation_id = await self.github_app_service.find_installation_for_repository(repository)
            if installation_id is None:
                raise Exception(f"Repository {repository} not accessible via any GitHub App installation")
            return await self.github_app_service.get_installation_token(installation_id)
        return None 