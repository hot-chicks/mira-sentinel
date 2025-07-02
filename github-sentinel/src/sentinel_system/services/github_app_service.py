"""
GitHub App authentication service for Sentinel System.

Handles GitHub App authentication, JWT generation, and installation token management.
"""

import time
import jwt
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class GitHubAppService:
    """Service for GitHub App authentication and token management."""
    
    def __init__(self):
        self.app_id = getattr(settings, 'GITHUB_APP_ID', None)
        self.private_key_path = getattr(settings, 'GITHUB_APP_PRIVATE_KEY_PATH', None)
        self.installation_id = getattr(settings, 'GITHUB_APP_INSTALLATION_ID', None)
        self.installation_ids = self._parse_installation_ids()
        self._private_key = None
        self._installation_token_cache = {}
        self._repository_installation_cache = {}  # Cache repo -> installation_id mapping
        
    def _parse_installation_ids(self) -> List[int]:
        """Parse installation IDs from configuration."""
        installation_ids = []
        
        # Check for multiple installation IDs first
        if hasattr(settings, 'GITHUB_APP_INSTALLATION_IDS') and settings.GITHUB_APP_INSTALLATION_IDS:
            ids_str = settings.GITHUB_APP_INSTALLATION_IDS.strip()
            if ids_str:
                try:
                    installation_ids = [int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()]
                except ValueError as e:
                    logger.error(f"Invalid installation IDs format: {ids_str}")
                    raise ValueError(f"Invalid installation IDs format: {e}")
        
        # Fallback to single installation ID for backward compatibility
        elif self.installation_id:
            try:
                installation_ids = [int(self.installation_id)]
            except ValueError as e:
                logger.error(f"Invalid installation ID: {self.installation_id}")
                raise ValueError(f"Invalid installation ID: {e}")
        
        logger.info(f"Configured with {len(installation_ids)} installation(s): {installation_ids}")
        return installation_ids
    
    def _load_private_key(self) -> str:
        """Load the GitHub App private key from file."""
        if self._private_key is None:
            if not self.private_key_path:
                raise ValueError("GITHUB_APP_PRIVATE_KEY_PATH not configured")
            
            try:
                with open(self.private_key_path, 'r') as key_file:
                    self._private_key = key_file.read()
                logger.info("GitHub App private key loaded successfully")
            except FileNotFoundError:
                raise FileNotFoundError(f"GitHub App private key file not found: {self.private_key_path}")
            except Exception as e:
                raise Exception(f"Failed to load GitHub App private key: {str(e)}")
        
        return self._private_key
    
    def generate_jwt_token(self) -> str:
        """
        Generate a JWT token for GitHub App authentication.
        
        Returns:
            JWT token string
        """
        if not self.app_id:
            raise ValueError("GITHUB_APP_ID not configured")
        
        private_key = self._load_private_key()
        
        # JWT payload
        now = int(time.time())
        payload = {
            'iat': now - 60,  # Issued at time (60 seconds ago to account for clock skew)
            'exp': now + (10 * 60),  # Expires in 10 minutes (GitHub's maximum)
            'iss': self.app_id  # Issuer (GitHub App ID)
        }
        
        try:
            # Generate JWT token
            token = jwt.encode(payload, private_key, algorithm='RS256')
            logger.debug("JWT token generated successfully")
            return token
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {str(e)}")
            raise
    
    async def get_installation_token(self, installation_id: Optional[int] = None) -> str:
        """
        Get an installation access token for the GitHub App.
        
        Args:
            installation_id: Installation ID (uses default if not provided)
            
        Returns:
            Installation access token
        """
        target_installation_id = installation_id or self.installation_id
        if not target_installation_id:
            raise ValueError("Installation ID not provided and GITHUB_APP_INSTALLATION_ID not configured")
        
        # Check cache for valid token
        cache_key = f"installation_{target_installation_id}"
        if cache_key in self._installation_token_cache:
            cached_token = self._installation_token_cache[cache_key]
            # Check if token is still valid (with 5 minute buffer)
            # Use UTC for comparison to avoid timezone issues
            current_time_utc = datetime.now(timezone.utc)
            if cached_token['expires_at'] > current_time_utc + timedelta(minutes=5):
                logger.debug(f"Using cached installation token for installation {target_installation_id}")
                return cached_token['token']
            else:
                # Remove expired token from cache
                del self._installation_token_cache[cache_key]
        
        # Generate new installation token
        jwt_token = self.generate_jwt_token()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"https://api.github.com/app/installations/{target_installation_id}/access_tokens",
                    headers={
                        "Authorization": f"Bearer {jwt_token}",
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "Sentinel-System/1.0"
                    }
                )
                
                if response.status_code == 201:
                    token_data = response.json()
                    access_token = token_data['token']
                    # Parse the expiration time and ensure it's UTC
                    expires_at_str = token_data['expires_at'].replace('Z', '+00:00')
                    expires_at = datetime.fromisoformat(expires_at_str).replace(tzinfo=timezone.utc)
                    
                    # Cache the token
                    self._installation_token_cache[cache_key] = {
                        'token': access_token,
                        'expires_at': expires_at
                    }
                    
                    logger.info(f"Generated new installation token for installation {target_installation_id}")
                    return access_token
                else:
                    error_msg = f"Failed to get installation token: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
            except httpx.RequestError as e:
                error_msg = f"Network error getting installation token: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
    
    async def get_authenticated_client(self, installation_id: Optional[int] = None) -> httpx.AsyncClient:
        """
        Get an authenticated HTTP client for GitHub API calls.
        
        Args:
            installation_id: Installation ID (uses default if not provided)
            
        Returns:
            Authenticated HTTP client
        """
        token = await self.get_installation_token(installation_id)
        
        return httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Sentinel-System/1.0"
            }
        )
    
    async def get_installation_repositories(self, installation_id: Optional[int] = None) -> list[Dict[str, Any]]:
        """
        Get all repositories accessible to the GitHub App installation.
        
        Args:
            installation_id: Installation ID (uses default if not provided)
            
        Returns:
            List of repository data
        """
        async with await self.get_authenticated_client(installation_id) as client:
            try:
                response = await client.get("https://api.github.com/installation/repositories")
                
                if response.status_code == 200:
                    data = response.json()
                    repositories = data.get('repositories', [])
                    logger.info(f"Found {len(repositories)} repositories in installation")
                    return repositories
                else:
                    error_msg = f"Failed to get installation repositories: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
            except httpx.RequestError as e:
                error_msg = f"Network error getting installation repositories: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
    
    async def check_app_health(self) -> Dict[str, Any]:
        """
        Check GitHub App authentication health.
        
        Returns:
            Health status dictionary
        """
        try:
            # Check if we can generate JWT token
            jwt_token = self.generate_jwt_token()
            jwt_valid = bool(jwt_token)
            
            # Check if we can get installation token
            installation_token = await self.get_installation_token()
            installation_valid = bool(installation_token)
            
            # Check if we can access repositories
            repositories = await self.get_installation_repositories()
            repo_access = len(repositories) > 0
            
            return {
                "github_app_configured": bool(self.app_id and self.private_key_path),
                "jwt_generation": jwt_valid,
                "installation_token": installation_valid,
                "repository_access": repo_access,
                "accessible_repositories": len(repositories),
                "status": "healthy" if all([jwt_valid, installation_valid, repo_access]) else "unhealthy"
            }
            
        except Exception as e:
            logger.error(f"GitHub App health check failed: {str(e)}")
            return {
                "github_app_configured": bool(self.app_id and self.private_key_path),
                "jwt_generation": False,
                "installation_token": False,
                "repository_access": False,
                "accessible_repositories": 0,
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def find_installation_for_repository(self, repository: str) -> Optional[int]:
        """
        Find the installation ID that has access to the specified repository.
        
        Args:
            repository: Repository full name (owner/repo)
            
        Returns:
            Installation ID that has access to the repository, or None if not found
        """
        # Check cache first
        if repository in self._repository_installation_cache:
            cached_installation_id = self._repository_installation_cache[repository]
            logger.debug(f"Using cached installation {cached_installation_id} for repository {repository}")
            return cached_installation_id
        
        # Search through all configured installations
        for installation_id in self.installation_ids:
            try:
                repositories = await self.get_installation_repositories(installation_id)
                accessible_repos = [repo["full_name"] for repo in repositories]
                
                if repository in accessible_repos:
                    logger.info(f"Found repository {repository} in installation {installation_id}")
                    # Cache the result
                    self._repository_installation_cache[repository] = installation_id
                    return installation_id
                    
            except Exception as e:
                logger.warning(f"Error checking installation {installation_id} for repository {repository}: {str(e)}")
                continue
        
        logger.warning(f"Repository {repository} not found in any configured installation")
        return None
    
    async def get_all_accessible_repositories(self) -> Dict[str, Any]:
        """
        Get all repositories accessible across all configured installations.
        
        Returns:
            Dictionary with installation details and repositories
        """
        all_repos = []
        installation_details = {}
        
        for installation_id in self.installation_ids:
            try:
                repositories = await self.get_installation_repositories(installation_id)
                repo_names = [repo["full_name"] for repo in repositories]
                
                installation_details[str(installation_id)] = {
                    "repositories": repo_names,
                    "count": len(repositories),
                    "status": "accessible"
                }
                
                all_repos.extend(repo_names)
                logger.info(f"Installation {installation_id}: {len(repositories)} repositories accessible")
                
            except Exception as e:
                logger.error(f"Error accessing installation {installation_id}: {str(e)}")
                installation_details[str(installation_id)] = {
                    "repositories": [],
                    "count": 0,
                    "status": "error",
                    "error": str(e)
                }
        
        return {
            "total_repositories": len(all_repos),
            "unique_repositories": len(set(all_repos)),  # Remove duplicates
            "installations": installation_details,
            "all_repositories": sorted(list(set(all_repos)))  # Unique sorted list
        } 