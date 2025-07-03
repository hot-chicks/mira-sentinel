"""
Issue processor service for Sentinel System.

Orchestrates the entire workflow from issue analysis to implementation.
Supports multi-repository operations with workspace management.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from .github_service import GitHubService
from .aider_service import AiderService
from .git_service import GitService
from .workspace_service import WorkspaceService
from ..config import settings

logger = logging.getLogger(__name__)


class IssueProcessor:
    """Service for processing GitHub issues with AI assistance and multi-repository support."""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.aider_service = AiderService()
        self.git_service = GitService()
        self.workspace_service = WorkspaceService()
    
    async def process_issue(self, issue_number: int, repository: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a GitHub issue through the complete workflow.
        
        Args:
            issue_number: The issue number to process
            repository: Repository full name (owner/repo) for multi-repo support
            
        Returns:
            Processing result dictionary
        """
        try:
            repo_context = f" in {repository}" if repository else ""
            logger.info(f"Starting processing for issue #{issue_number}{repo_context}")
            
            # Get the issue details
            issue = await self.github_service.get_issue(issue_number, repository)
            issue_title = issue["title"]
            issue_body = issue.get("body", "")
            labels = [label["name"] for label in issue.get("labels", [])]
            
            logger.info(f"Processing issue #{issue_number}{repo_context}: {issue_title}")
            
            # Check if issue is in correct state
            if settings.GITHUB_WORKING_LABEL in labels:
                logger.warning(f"Issue #{issue_number}{repo_context} is already being processed")
                return {"status": "already_processing", "message": "Issue is already being processed"}
            
            # Add working label
            await self.github_service.add_label(issue_number, settings.GITHUB_WORKING_LABEL, repository)
            
            try:
                # Check if this is a proposal phase or implementation phase
                if settings.GITHUB_APPROVED_LABEL in labels:
                    # Implementation phase
                    result = await self._implement_approved_solution(issue_number, issue_title, issue_body, repository)
                else:
                    # Analysis and proposal phase
                    result = await self._analyze_and_propose(issue_number, issue_title, issue_body, repository)
                
                # Remove working label on success
                await self.github_service.remove_label(issue_number, settings.GITHUB_WORKING_LABEL, repository)
                
                logger.info(f"Successfully processed issue #{issue_number}{repo_context}")
                return result
                
            except Exception as e:
                # Remove working label on error
                await self.github_service.remove_label(issue_number, settings.GITHUB_WORKING_LABEL, repository)
                
                # Add error comment
                error_comment = f"🚨 **Sentinel System - Processing Error**\n\nAn error occurred while processing this issue:\n\n```\n{str(e)}\n```\n\nPlease check the system logs for more details."
                await self.github_service.add_comment(issue_number, error_comment, repository)
                
                raise
            
        except Exception as e:
            logger.error(f"Error processing issue #{issue_number}{repo_context}: {str(e)}")
            raise
    
    async def _analyze_and_propose(self, issue_number: int, issue_title: str, issue_body: str, repository: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze issue and create proposal.
        
        Args:
            issue_number: Issue number
            issue_title: Issue title
            issue_body: Issue description
            repository: Repository full name (owner/repo)
            
        Returns:
            Analysis result
        """
        workspace_dir = None
        try:
            repo_context = f" in {repository}" if repository else ""
            logger.info(f"Analyzing issue #{issue_number}{repo_context}")
            
            # Create workspace and clone repository for analysis
            workspace_dir = await self.workspace_service.create_workspace(repository, issue_number)
            repo_dir = await self.workspace_service.clone_repository(repository, workspace_dir)
            
            # Prepare issue data for AiderService
            issue_data = {
                "number": issue_number,
                "title": issue_title,
                "body": issue_body
            }
            
            # Get AI analysis and proposal using AiderService
            analysis_result = await self.aider_service.analyze_issue(issue_data, repo_dir, repository)
            
            if not analysis_result.get("success"):
                raise Exception(f"Aider analysis failed: {analysis_result.get('error', 'Unknown error')}")
            
            proposal = analysis_result.get("analysis", "")
            
            # Create clean, professional proposal comment
            comment = f"""🤖 **Sentinel System - Issue Analysis & Proposal**

{proposal}

---

**⚠️ IMPORTANT**: This is a PROPOSAL only. No code changes have been made yet.

**Next Steps:**
- 👍 **Approve**: Add the `{settings.GITHUB_APPROVED_LABEL}` label to proceed with implementation
- 👎 **Request Changes**: Remove the `{settings.GITHUB_PROPOSAL_LABEL}` label and add feedback comments
- 🔄 **Refine**: I'll update the proposal based on your feedback

Once approved, I'll implement the solution and create a pull request.

*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
            
            # Add comment to issue
            await self.github_service.add_comment(issue_number, comment, repository)
            
            # Add proposal pending label
            await self.github_service.add_label(issue_number, settings.GITHUB_PROPOSAL_LABEL, repository)
            
            # Remove ready label since we've started processing
            await self.github_service.remove_label(issue_number, settings.GITHUB_ISSUE_LABEL, repository)
            
            logger.info(f"Created proposal for issue #{issue_number}{repo_context}")
            
            return {
                "status": "proposal_created",
                "message": "AI proposal created and awaiting human review",
                "proposal": proposal,
                "repository": repository
            }
            
        except Exception as e:
            logger.error(f"Error analyzing issue #{issue_number}{repo_context}: {str(e)}")
            raise
        finally:
            # Clean up workspace
            if workspace_dir:
                await self.workspace_service.cleanup_workspace(workspace_dir)
    
    async def _implement_approved_solution(self, issue_number: int, issue_title: str, issue_body: str, repository: Optional[str] = None) -> Dict[str, Any]:
        """
        Implement the approved solution.
        
        Args:
            issue_number: Issue number
            issue_title: Issue title
            issue_body: Issue description
            repository: Repository full name (owner/repo)
            
        Returns:
            Implementation result
        """
        workspace_dir = None
        try:
            repo_context = f" in {repository}" if repository else ""
            logger.info(f"Implementing approved solution for issue #{issue_number}{repo_context}")
            
            # Create workspace and clone repository for implementation
            workspace_dir = await self.workspace_service.create_workspace(repository, issue_number)
            repo_dir = await self.workspace_service.clone_repository(repository, workspace_dir)
            
            # Get the approved proposal from comments
            approved_proposal = await self._get_approved_proposal(issue_number, repository)
            
            # Prepare issue data for AiderService
            issue_data = {
                "number": issue_number,
                "title": issue_title,
                "body": issue_body
            }
            
            # Create branch for this issue in the workspace
            branch_name = f"{settings.GIT_BRANCH_PREFIX}{issue_number}"
            await self.git_service.create_branch(branch_name, repo_dir)
            
            # Get AI to implement the solution using AiderService legacy method
            # This method works with dictionaries instead of issue objects
            implementation_result = await self.aider_service.implement_solution_legacy(
                issue_data, approved_proposal, repo_dir, repository
            )
            
            # The legacy implement_solution method returns a dictionary
            if not implementation_result.get("success"):
                raise Exception(f"Aider implementation failed: {implementation_result.get('error', 'Unknown error')}")
            
            implementation = implementation_result.get("implementation", "")
            changes_made = implementation_result.get("changes_made", False)
            
            # Check if there are any changes to commit
            has_changes = await self.git_service.has_changes(repo_dir)
            
            if has_changes and changes_made:
                # Commit changes
                commit_message = f"Implement solution for issue #{issue_number}: {issue_title[:50]}"
                success = await self.git_service.commit_changes(repo_dir, commit_message)
                
                if not success:
                    logger.warning(f"No changes to commit for issue #{issue_number}")
                    # Still continue with creating PR even if no changes to commit
                
                # Push changes
                await self.git_service.push_branch(branch_name, repo_dir)
                
                # Create pull request
                pr_title = f"Fix issue #{issue_number}: {issue_title}"
                pr_body = f"""Resolves #{issue_number}

## Implementation Summary

{implementation}

## Changes Made
- Implemented solution as approved in issue #{issue_number}
- All changes are focused on resolving the specific issue

**Auto-generated by Sentinel System**
"""
                
                pr = await self.github_service.create_pull_request(
                    title=pr_title,
                    body=pr_body,
                    head=branch_name,
                    base="main",
                    repository=repository
                )
                
                # Add completion comment to issue
                completion_comment = f"""✅ **Sentinel System - Implementation Complete**

## Solution Implemented

{implementation}

## Pull Request Created
🔗 **Pull Request:** {pr['html_url']}

The solution has been implemented and is ready for review. The PR contains all necessary changes to resolve this issue.

*Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
                
                await self.github_service.add_comment(issue_number, completion_comment, repository)
                
                # Remove labels
                await self.github_service.remove_label(issue_number, settings.GITHUB_APPROVED_LABEL, repository)
                
                logger.info(f"Successfully implemented solution for issue #{issue_number}{repo_context}, PR: {pr['html_url']}")
                
                return {
                    "status": "implemented",
                    "message": "Solution implemented and PR created",
                    "pull_request_url": pr['html_url'],
                    "branch": branch_name
                }
            else:
                # No changes were made
                no_changes_comment = f"""ℹ️ **Sentinel System - No Changes Required**

After analyzing the issue and attempting implementation, no code changes were required. This might mean:

- The issue was already resolved
- The solution doesn't require code changes
- The issue needs clarification

{implementation}

*Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
                
                await self.github_service.add_comment(issue_number, no_changes_comment, repository)
                await self.github_service.remove_label(issue_number, settings.GITHUB_APPROVED_LABEL, repository)
                
                return {
                    "status": "no_changes",
                    "message": "No code changes were required",
                    "implementation": implementation
                }
            
        except Exception as e:
            logger.error(f"Error implementing solution for issue #{issue_number}{repo_context}: {str(e)}")
            raise
        finally:
            # Clean up workspace
            if workspace_dir:
                await self.workspace_service.cleanup_workspace(workspace_dir)
    
    async def refine_proposal(self, issue_number: int, feedback: str, repository: Optional[str] = None) -> Dict[str, Any]:
        """
        Refine a proposal based on human feedback.
        
        Args:
            issue_number: Issue number
            feedback: Human feedback on the proposal
            repository: Repository full name (owner/repo)
            
        Returns:
            Refinement result
        """
        workspace_dir = None
        try:
            repo_context = f" in {repository}" if repository else ""
            logger.info(f"Refining proposal for issue #{issue_number}{repo_context}")
            
            # Get issue details
            issue = await self.github_service.get_issue(issue_number, repository)
            issue_title = issue["title"]
            issue_body = issue.get("body", "")
            
            # Create workspace and clone repository for refinement
            workspace_dir = await self.workspace_service.create_workspace(repository, issue_number)
            repo_dir = await self.workspace_service.clone_repository(repository, workspace_dir)
            
            # Prepare issue data for AiderService
            issue_data = {
                "number": issue_number,
                "title": issue_title,
                "body": issue_body
            }
            
            # For now, use placeholder for previous proposal
            # In real implementation, we'd parse comments to get the previous proposal
            previous_proposal = "Previous proposal from earlier analysis"
            
            # Get refined proposal using AiderService
            refinement_result = await self.aider_service.refine_proposal(
                issue_data, previous_proposal, feedback, repo_dir, repository
            )
            
            if not refinement_result.get("success"):
                raise Exception(f"Aider proposal refinement failed: {refinement_result.get('error', 'Unknown error')}")
            
            refined_proposal = refinement_result.get("refined_proposal", "")
            
            # Create refined proposal comment
            comment = f"""🔄 **Sentinel System - Refined Proposal**

Based on your feedback, I've refined my proposal:

## Refined Solution

{refined_proposal}

---

**Next Steps:**
- 👍 If you approve this refined proposal, add the `{settings.GITHUB_APPROVED_LABEL}` label
- 👎 If you want further changes, provide additional feedback

*Refined at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
            
            # Add refined proposal comment
            await self.github_service.add_comment(issue_number, comment, repository)
            
            # Re-add proposal pending label
            await self.github_service.add_label(issue_number, settings.GITHUB_PROPOSAL_LABEL, repository)
            
            logger.info(f"Refined proposal for issue #{issue_number}{repo_context}")
            
            return {
                "status": "proposal_refined",
                "message": "Proposal refined based on feedback",
                "refined_proposal": refined_proposal
            }
            
        except Exception as e:
            logger.error(f"Error refining proposal for issue #{issue_number}{repo_context}: {str(e)}")
            raise
        finally:
            # Clean up workspace
            if workspace_dir:
                await self.workspace_service.cleanup_workspace(workspace_dir)
    
    async def _get_approved_proposal(self, issue_number: int, repository: Optional[str] = None) -> str:
        """
        Get the approved proposal from GitHub issue comments.
        
        Args:
            issue_number: Issue number
            repository: Repository full name (owner/repo)
            
        Returns:
            The approved proposal text
        """
        try:
            # Get issue comments
            repo = self.github_service._get_repo_for_request(repository)
            
            async with await self.github_service._get_authenticated_client(repository) as client:
                response = await client.get(
                    f"{self.github_service.base_url}/repos/{repo}/issues/{issue_number}/comments"
                )
                response.raise_for_status()
                comments = response.json()
            
            # Look for the latest Sentinel System proposal comment
            for comment in reversed(comments):  # Start from most recent
                body = comment.get("body", "")
                if "🤖 **Sentinel System - Issue Analysis & Proposal**" in body:
                    # Extract the proposal content
                    lines = body.split('\n')
                    proposal_lines = []
                    capturing = False
                    
                    for line in lines:
                        if "## My Understanding & Proposed Solution" in line:
                            capturing = True
                            continue
                        elif capturing and line.startswith("---"):
                            break
                        elif capturing:
                            proposal_lines.append(line)
                    
                    if proposal_lines:
                        return '\n'.join(proposal_lines).strip()
            
            # Fallback if no proposal found
            return "No previous proposal found. Please analyze the issue requirements and implement accordingly."
            
        except Exception as e:
            logger.error(f"Error getting approved proposal for issue #{issue_number}: {str(e)}")
            return "Error retrieving proposal. Please analyze the issue requirements and implement accordingly." 