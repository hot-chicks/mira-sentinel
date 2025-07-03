"""
Aider service for Sentinel System.

Provides AI-powered code analysis and implementation using Aider CLI with Claude Sonnet 4.
Handles GitHub issue analysis, solution proposals, and automated implementation.
"""

import asyncio
import glob
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# Import GitHub Issue type for type hints
try:
    from github import Issue
except ImportError:
    # Fallback if PyGithub is not available
    Issue = Any

class AiderService:
    """Service for AI-powered code analysis and implementation using Aider CLI."""
    
    def __init__(self):
        self.model = "claude-sonnet-4-20250514"  # Sonnet 4 model
        self.api_key = settings.ANTHROPIC_API_KEY
        
    async def check_availability(self) -> Dict[str, Any]:
        """
        Check if Aider CLI is available and properly configured.
        
        Returns:
            Dictionary with availability status and details
        """
        try:
            # Check if aider command exists
            result = await self._run_command(["aider", "--version"], check_api_key=False)
            
            if result["success"]:
                version_output = result["output"]
                logger.info(f"Aider CLI available: {version_output.strip()}")
                
                # Check API key configuration
                api_key_configured = bool(self.api_key)
                
                return {
                    "available": True,
                    "version": version_output.strip(),
                    "model": self.model,
                    "api_key_configured": api_key_configured,
                    "authenticated": api_key_configured  # Assume valid if configured
                }
            else:
                logger.error(f"Aider CLI not available: {result['error']}")
                return {
                    "available": False,
                    "error": result["error"]
                }
                
        except Exception as e:
            logger.error(f"Error checking Aider availability: {str(e)}")
            return {
                "available": False,
                "error": str(e)
            }
    
    async def analyze_issue(
        self, 
        issue_data: Dict[str, Any], 
        repository_path: Path,
        repository: str
    ) -> Dict[str, Any]:
        """
        Analyze a GitHub issue using Aider in dry-run mode with clean output formatting.
        
        Args:
            issue_data: GitHub issue data dictionary
            repository_path: Path to the cloned repository
            repository: Repository full name (owner/repo)
            
        Returns:
            Dictionary with analysis results
        """
        try:
            issue_number = issue_data.get("number")
            issue_title = issue_data.get("title", "")
            issue_body = issue_data.get("body", "")
            
            logger.info(f"Analyzing issue #{issue_number} in {repository} using Aider")
            
            # Get relevant files for context
            relevant_files = await self._get_relevant_files(repository_path)
            
            # Prepare Aider command for analysis (dry-run mode)
            cmd = [
                "aider",
                "--model", self.model,
                "--dry-run",          # Analysis mode - no actual changes
                "--no-auto-commits",  # We'll handle commits ourselves
                "--no-check-update",  # Don't check for updates
                "--disable-playwright",  # Don't install Playwright
                "--no-suggest-shell-commands",  # Don't suggest shell commands
                "--yes",              # Auto-confirm prompts
                "--no-stream",        # Don't stream output
                "--no-pretty",        # Disable pretty output formatting
            ]
            
            # Add relevant files for context
            if relevant_files:
                cmd.extend(relevant_files)
            
            # Set environment variables to prevent installations
            env = os.environ.copy()
            env.update({
                "AIDER_DISABLE_PLAYWRIGHT": "1",  # Disable Playwright installation
                "PYTHONPATH": str(repository_path),
            })
            
            # Create professional analysis prompt
            prompt = f"""Please analyze this GitHub issue and provide a clean, professional proposal in this EXACT format:

## 🔍 Problem Analysis
[Describe what needs to be implemented/fixed in 2-3 clear sentences]

## 💡 Solution Approach
[Explain the high-level approach to solve this problem]

## 📋 Implementation Plan
1. [First step - be specific and actionable]
2. [Second step - be specific and actionable]  
3. [Continue with numbered steps...]

## 📁 Files to Create/Modify
- `filename.ext` - Brief description of what this file does
- `another-file.ext` - Brief description of what this file does

## ⚠️ Dependencies & Considerations
[List any requirements, dependencies, or important considerations]

---

**Issue #{issue_number}: {issue_title}**

**Description:**
{issue_body or "No description provided"}

IMPORTANT INSTRUCTIONS:
- Use ONLY the format above
- Do NOT include token costs, technical metadata, or debugging info
- Do NOT include SEARCH/REPLACE blocks or code examples
- Do NOT include error messages or Aider-specific details
- Keep it professional and human-readable
- Focus on WHAT needs to be done, not HOW to do it technically
- Be concise but comprehensive
"""

            # Run Aider analysis
            raw_result = await self._run_aider_command(
                cmd, 
                repository_path, 
                prompt,
                env=env
            )
            
            # Clean and format the output
            clean_analysis = await self._clean_aider_output(raw_result)
            
            # Clean up any files that might have been downloaded during analysis
            await self._cleanup_unwanted_files(repository_path)
            
            return {
                "success": True,
                "analysis": clean_analysis,
                "issue_number": issue_number,
                "repository": repository
            }
            
        except Exception as e:
            logger.error(f"Error analyzing issue with Aider: {e}")
            return {
                "success": False,
                "error": str(e),
                "issue_number": issue_data.get("number"),
                "repository": repository
            }
    
    async def implement_solution(self, issue: Issue, repo_dir: Path, repository: str) -> str:
        """
        Implement the approved solution using Aider.
        
        Args:
            issue: GitHub issue object
            repo_dir: Repository directory path
            repository: Repository full name (owner/repo)
            
        Returns:
            Implementation result message
        """
        try:
            logger.info(f"Implementing solution for issue #{issue.number} in {repository} using Aider")
            
            # Get the approved proposal
            proposal = await self._get_approved_proposal(issue, repository)
            if not proposal:
                return "No approved proposal found for implementation"
            
            # Get relevant files for context
            relevant_files = await self._get_relevant_files(repo_dir)
            
            # Prepare Aider command for implementation
            cmd = [
                "aider",
                "--model", self.model,
                "--no-auto-commits",  # We'll handle commits ourselves
                "--no-check-update",  # Don't check for updates
                "--disable-playwright",  # Don't install Playwright
                "--no-suggest-shell-commands",  # Don't suggest shell commands
                "--yes",              # Auto-confirm prompts
                "--no-stream",        # Don't stream output
                "--auto-test", "false",  # Don't run tests automatically
            ]
            
            # Add relevant files for context
            if relevant_files:
                cmd.extend(relevant_files)
            
            # Set environment variables to prevent installations
            env = os.environ.copy()
            env.update({
                "AIDER_DISABLE_PLAYWRIGHT": "1",  # Disable Playwright installation
                "PYTHONPATH": str(repo_dir),
            })
            
            # Create implementation prompt - be more direct and specific
            prompt = f"""You are implementing an approved solution. Create the necessary files immediately without asking for confirmation.

**Issue #{issue.number}**

**Approved Solution to Implement:**
{proposal}

**DIRECT IMPLEMENTATION INSTRUCTIONS:**
1. CREATE the files specified in the proposal immediately
2. DO NOT ask for confirmation or permission
3. DO NOT explain what you're going to do - just do it
4. Follow the project structure and conventions
5. Focus on creating documentation and code files only
6. Do NOT install packages or download external files

**IMPORTANT:** This is an approved solution. Implement it now by creating the required files."""

            # Run Aider with the implementation prompt
            result = await self._run_aider_command(
                cmd, 
                repo_dir, 
                prompt,
                env=env
            )
            
            # Clean up any downloaded files that shouldn't be committed
            await self._cleanup_unwanted_files(repo_dir)
            
            return f"Solution implemented successfully using Aider"
            
        except Exception as e:
            logger.error(f"Error implementing solution with Aider: {e}")
            return f"Implementation failed: {str(e)}"
    
    async def refine_proposal(
        self,
        issue_data: Dict[str, Any],
        previous_proposal: str,
        feedback: str,
        repository_path: Path,
        repository: str
    ) -> Dict[str, Any]:
        """
        Refine a proposal based on human feedback.
        
        Args:
            issue_data: GitHub issue data
            previous_proposal: Previous implementation proposal
            feedback: Human feedback on the proposal
            repository_path: Path to the cloned repository
            repository: Repository full name (owner/repo)
            
        Returns:
            Dictionary with refined proposal results
        """
        try:
            issue_number = issue_data.get("number")
            issue_title = issue_data.get("title", "")
            
            logger.info(f"Refining proposal for issue #{issue_number} in {repository} using Aider")
            
            # Prepare refinement prompt with clean format
            refinement_prompt = f"""Please refine this GitHub issue proposal based on human feedback, using this EXACT format:

## 🔍 Problem Analysis
[Updated analysis based on feedback - 2-3 clear sentences]

## 💡 Solution Approach
[Refined high-level approach addressing the feedback]

## 📋 Implementation Plan
1. [Updated first step - be specific and actionable]
2. [Updated second step - be specific and actionable]  
3. [Continue with numbered steps...]

## 📁 Files to Create/Modify
- `filename.ext` - Brief description of what this file does
- `another-file.ext` - Brief description of what this file does

## ⚠️ Dependencies & Considerations
[Updated requirements, dependencies, or important considerations]

---

**Issue #{issue_number}: {issue_title}**

**Previous Proposal:**
{previous_proposal}

**Human Feedback:**
{feedback}

IMPORTANT INSTRUCTIONS:
- Use ONLY the format above
- Address ALL points raised in the feedback
- Do NOT include token costs, technical metadata, or debugging info
- Do NOT include SEARCH/REPLACE blocks or code examples
- Do NOT include error messages or Aider-specific details
- Keep it professional and human-readable
- Focus on WHAT needs to be done, not HOW to do it technically
- Be concise but comprehensive
"""

            # Get relevant files for context
            relevant_files = await self._get_relevant_files(repository_path)
            
            # Prepare Aider command for refinement (dry-run mode)
            cmd = [
                "aider",
                "--model", self.model,
                "--dry-run",          # Analysis mode - no actual changes
                "--no-auto-commits",  # We'll handle commits ourselves
                "--no-check-update",  # Don't check for updates
                "--disable-playwright",  # Don't install Playwright
                "--no-suggest-shell-commands",  # Don't suggest shell commands
                "--yes",              # Auto-confirm prompts
                "--no-stream",        # Don't stream output
                "--no-pretty",        # Disable pretty output formatting
            ]
            
            # Add relevant files for context
            if relevant_files:
                cmd.extend(relevant_files)
            
            # Set environment variables to prevent installations
            env = os.environ.copy()
            env.update({
                "AIDER_DISABLE_PLAYWRIGHT": "1",  # Disable Playwright installation
                "PYTHONPATH": str(repository_path),
            })
            
            # Run Aider refinement
            raw_result = await self._run_aider_command(
                cmd,
                repository_path,
                refinement_prompt,
                env=env
            )
            
            # Clean and format the output
            clean_refined_proposal = await self._clean_aider_output(raw_result)
            
            return {
                "success": True,
                "refined_proposal": clean_refined_proposal,
                "issue_number": issue_number,
                "repository": repository
            }
                
        except Exception as e:
            logger.error(f"Error refining proposal for issue #{issue_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "issue_number": issue_number,
                "repository": repository
            }
    
    async def _run_aider_command(
        self,
        cmd: list,
        repo_dir: Path,
        prompt: str,
        env: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Run an Aider command with the specified parameters.
        
        Args:
            cmd: Aider command list
            repo_dir: Repository directory path
            prompt: Prompt message for Aider
            env: Environment variables
            
        Returns:
            Command output as string
        """
        try:
            # Add the prompt as message to the command
            final_cmd = cmd + ["--message", prompt]
            
            logger.debug(f"Running Aider command: {' '.join(final_cmd[:4])}... (message truncated)")
            
            # Run command in repository directory with custom environment
            result = await self._run_command(final_cmd, cwd=repo_dir, env=env)
            
            if result["success"]:
                return result["output"]
            else:
                raise Exception(result["error"])
            
        except Exception as e:
            logger.error(f"Error running Aider command: {str(e)}")
            raise e
    
    async def _get_relevant_files(self, repository_path: Path) -> list:
        """
        Get relevant files to add to Aider context for better understanding.
        
        Args:
            repository_path: Path to the repository
            
        Returns:
            List of file paths to include in Aider context
        """
        relevant_files = []
        
        try:
            # Always include README if it exists
            for readme_name in ["README.md", "README.rst", "README.txt", "readme.md"]:
                readme_path = repository_path / readme_name
                if readme_path.exists():
                    relevant_files.append(str(readme_path))
                    break
            
            # Include package.json, requirements.txt, pyproject.toml etc for project structure
            for config_file in ["package.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod"]:
                config_path = repository_path / config_file
                if config_path.exists():
                    relevant_files.append(str(config_path))
            
            # Include main source files (limit to avoid too many files)
            src_patterns = [
                "src/**/*.py",
                "lib/**/*.py", 
                "*.py",
                "src/**/*.js",
                "src/**/*.ts",
                "*.js",
                "*.ts"
            ]
            
            file_count = 0
            for pattern in src_patterns:
                for file_path in repository_path.glob(pattern):
                    if file_path.is_file() and file_count < 10:  # Limit to avoid overwhelming Aider
                        relevant_files.append(str(file_path))
                        file_count += 1
                    if file_count >= 10:
                        break
                if file_count >= 10:
                    break
            
            logger.debug(f"Selected {len(relevant_files)} relevant files for Aider context")
            return relevant_files
            
        except Exception as e:
            logger.error(f"Error getting relevant files: {str(e)}")
            return []
    
    async def _run_command(
        self,
        cmd: list,
        cwd: Optional[Path] = None,
        check_api_key: bool = True,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Run a shell command asynchronously.
        
        Args:
            cmd: Command and arguments
            cwd: Working directory
            check_api_key: Whether to check API key configuration
            env: Custom environment variables
            
        Returns:
            Dictionary with command results
        """
        try:
            # Set up environment
            command_env = os.environ.copy()
            if check_api_key and self.api_key:
                command_env["ANTHROPIC_API_KEY"] = self.api_key
            
            # Add custom environment variables if provided
            if env:
                command_env.update(env)
            
            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=command_env
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode('utf-8', errors='ignore').strip()
                logger.debug(f"Command succeeded: {output[:200]}...")
                return {
                    "success": True,
                    "output": output,
                    "returncode": process.returncode
                }
            else:
                error = stderr.decode('utf-8', errors='ignore').strip()
                logger.error(f"Command failed: {error}")
                return {
                    "success": False,
                    "error": error,
                    "returncode": process.returncode
                }
                
        except Exception as e:
            logger.error(f"Error running command: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _cleanup_unwanted_files(self, repo_dir: Path) -> None:
        """
        Clean up unwanted files that Aider might have downloaded.
        
        Args:
            repo_dir: Repository directory path
        """
        try:
            unwanted_patterns = [
                "*.deb",           # Debian packages like pandoc
                "*.rpm",           # RPM packages
                "*.tar.gz",        # Compressed archives
                "*.zip",           # Zip files
                "*.exe",           # Windows executables
                "*.msi",           # Windows installers
                "pandoc*",         # Pandoc files
                "playwright*",     # Playwright files
                "node_modules/",   # Node modules
                ".cache/",         # Cache directories
                "__pycache__/",    # Python cache
            ]
            
            for pattern in unwanted_patterns:
                # Use glob to find matching files
                matches = glob.glob(str(repo_dir / pattern), recursive=True)
                for match in matches:
                    match_path = Path(match)
                    if match_path.exists():
                        if match_path.is_file():
                            logger.info(f"Removing unwanted file: {match_path}")
                            match_path.unlink()
                        elif match_path.is_dir():
                            logger.info(f"Removing unwanted directory: {match_path}")
                            shutil.rmtree(match_path)
                            
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
            # Don't fail the whole process for cleanup errors 

    async def _get_approved_proposal(self, issue: Issue, repository: str) -> Optional[str]:
        """
        Get the approved proposal from GitHub issue comments.
        
        Args:
            issue: GitHub issue object
            repository: Repository full name (owner/repo)
            
        Returns:
            Approved proposal text or None if not found
        """
        try:
            # Look for Sentinel System analysis comments
            for comment in issue.get_comments():
                if "🤖 **Sentinel System - Issue Analysis & Proposal**" in comment.body:
                    # Extract the proposal section
                    lines = comment.body.split('\n')
                    proposal_lines = []
                    in_proposal = False
                    
                    for line in lines:
                        if "## 📋 **Implementation Proposal**" in line:
                            in_proposal = True
                            continue
                        elif line.startswith("## ") and in_proposal:
                            # End of proposal section
                            break
                        elif in_proposal:
                            proposal_lines.append(line)
                    
                    if proposal_lines:
                        proposal = '\n'.join(proposal_lines).strip()
                        logger.info(f"Found approved proposal for issue #{issue.number}")
                        return proposal
            
            # Fallback: use issue body if no specific proposal found
            logger.warning(f"No approved proposal found for issue #{issue.number}, using issue body")
            return issue.body or "No description provided"
            
        except Exception as e:
            logger.error(f"Error getting approved proposal: {e}")
            return issue.body or "No description provided"

    # Backwards compatibility method for issue_processor
    async def implement_solution_legacy(
        self,
        issue_data: Dict[str, Any],
        proposal: str,
        repository_path: Path,
        repository: str
    ) -> Dict[str, Any]:
        """
        Legacy implement_solution method for backwards compatibility.
        
        Args:
            issue_data: GitHub issue data dictionary
            proposal: Implementation proposal
            repository_path: Path to the cloned repository
            repository: Repository full name (owner/repo)
            
        Returns:
            Dictionary with implementation results
        """
        try:
            issue_number = issue_data.get("number")
            issue_title = issue_data.get("title", "")
            issue_body = issue_data.get("body", "")
            
            logger.info(f"Implementing solution for issue #{issue_number} in {repository} using Aider")
            
            # Get relevant files for context
            relevant_files = await self._get_relevant_files(repository_path)
            
            # Prepare Aider command for implementation
            cmd = [
                "aider",
                "--model", self.model,
                "--no-auto-commits",  # We'll handle commits ourselves
                "--no-check-update",  # Don't check for updates
                "--disable-playwright",  # Don't install Playwright
                "--no-suggest-shell-commands",  # Don't suggest shell commands
                "--yes",              # Auto-confirm prompts
                "--no-stream",        # Don't stream output
            ]
            
            # Add relevant files for context
            if relevant_files:
                cmd.extend(relevant_files)
            
            # Set environment variables to prevent installations
            env = os.environ.copy()
            env.update({
                "AIDER_DISABLE_PLAYWRIGHT": "1",  # Disable Playwright installation
                "PYTHONPATH": str(repository_path),
            })
            
            # Create implementation prompt - be more direct and specific
            prompt = f"""You are implementing an approved solution. Create the necessary files immediately without asking for confirmation.

**Issue #{issue_number}: {issue_title}**

**Approved Solution to Implement:**
{proposal}

**DIRECT IMPLEMENTATION INSTRUCTIONS:**
1. CREATE the files specified in the proposal immediately
2. DO NOT ask for confirmation or permission
3. DO NOT explain what you're going to do - just do it
4. Follow the project structure and conventions
5. Focus on creating documentation and code files only
6. Do NOT install packages or download external files

**IMPORTANT:** This is an approved solution. Implement it now by creating the required files."""

            # Run Aider with the implementation prompt
            result = await self._run_aider_command(
                cmd, 
                repository_path, 
                prompt,
                env=env
            )
            
            # Clean up any downloaded files that shouldn't be committed
            await self._cleanup_unwanted_files(repository_path)
            
            return {
                "success": True,
                "implementation": result,
                "changes_made": True,
                "issue_number": issue_number,
                "repository": repository
            }
            
        except Exception as e:
            logger.error(f"Error implementing solution with Aider: {e}")
            return {
                "success": False,
                "error": str(e),
                "changes_made": False,
                "issue_number": issue_data.get("number"),
                "repository": repository
            }

    async def _clean_aider_output(self, raw_output: str) -> str:
        """
        Clean and format Aider output for human consumption.
        
        Args:
            raw_output: Raw output from Aider command
            
        Returns:
            Cleaned and formatted analysis
        """
        try:
            # Remove Aider metadata and technical noise
            lines = raw_output.split('\n')
            cleaned_lines = []
            
            # Flags to track what we're filtering
            skip_until_analysis = True
            in_token_info = False
            in_search_replace = False
            in_error_block = False
            
            for line in lines:
                line_lower = line.lower().strip()
                
                # Skip initial Aider setup messages
                if skip_until_analysis:
                    if line.startswith('## 🔍') or line.startswith('## Problem Analysis'):
                        skip_until_analysis = False
                        cleaned_lines.append(line)
                    continue
                
                # Skip token cost information
                if 'tokens:' in line_lower and ('sent' in line_lower or 'received' in line_lower):
                    in_token_info = True
                    continue
                if in_token_info and line.strip() == '':
                    in_token_info = False
                    continue
                if in_token_info:
                    continue
                
                # Skip SEARCH/REPLACE blocks
                if '<<<<<<< SEARCH' in line or 'SEARCH' in line and '<<<<<<' in line:
                    in_search_replace = True
                    continue
                if in_search_replace and ('REPLACE' in line or '>>>>>>>' in line):
                    in_search_replace = False
                    continue
                if in_search_replace:
                    continue
                
                # Skip error blocks and technical details
                if any(keyword in line_lower for keyword in [
                    'aider v', 'main model:', 'weak model:', 'git repo:', 'repo-map:',
                    'searchreplacenoexactmatch', 'the llm did not conform',
                    'failed to match', 'only 3 reflections', 'stopping',
                    'did not apply edit', 'fix any errors below'
                ]):
                    continue
                
                # Skip lines that are clearly technical noise
                if any(pattern in line_lower for pattern in [
                    'you can skip this check',
                    'added .aider',
                    'don\'t re-send them',
                    'just reply with fixed versions',
                    'the search section must exactly match'
                ]):
                    continue
                
                # Keep the line if it passed all filters
                cleaned_lines.append(line)
            
            # Join cleaned lines and remove excessive whitespace
            cleaned_output = '\n'.join(cleaned_lines)
            
            # Remove multiple consecutive empty lines
            cleaned_output = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_output)
            
            # If the output is still messy or doesn't follow our format, create a fallback
            if not self._is_well_formatted_analysis(cleaned_output):
                logger.warning("Aider output doesn't follow expected format, creating fallback")
                return self._create_fallback_analysis(cleaned_output)
            
            return cleaned_output.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning Aider output: {e}")
            # Return a basic fallback if cleaning fails
            return self._create_fallback_analysis(raw_output)
    
    def _is_well_formatted_analysis(self, output: str) -> bool:
        """
        Check if the analysis output follows our expected format.
        
        Args:
            output: Cleaned output to check
            
        Returns:
            True if well-formatted, False otherwise
        """
        required_sections = [
            '## 🔍',  # Problem Analysis
            '## 💡',  # Solution Approach
            '## 📋',  # Implementation Plan
            '## 📁',  # Files to Create/Modify
        ]
        
        return all(section in output for section in required_sections)
    
    def _create_fallback_analysis(self, raw_output: str) -> str:
        """
        Create a fallback analysis when Aider output is too messy.
        
        Args:
            raw_output: Raw output from Aider
            
        Returns:
            Fallback formatted analysis
        """
        # Extract any meaningful content from the raw output
        meaningful_content = []
        lines = raw_output.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not any(skip_pattern in line.lower() for skip_pattern in [
                'tokens:', 'cost:', 'aider v', 'model:', 'git repo:', 'search', 'replace'
            ]):
                meaningful_content.append(line)
        
        # Create a basic structured format
        return f"""## 🔍 Problem Analysis
Based on the issue description, this requires implementation of the requested feature or fix.

## 💡 Solution Approach
The solution will involve creating or modifying the necessary files to address the issue requirements.

## 📋 Implementation Plan
1. Analyze the current codebase structure
2. Identify the files that need to be created or modified
3. Implement the required changes following project conventions
4. Test the implementation to ensure it works correctly

## 📁 Files to Create/Modify
- Files will be determined based on the specific requirements of the issue

## ⚠️ Dependencies & Considerations
- Follow existing project structure and conventions
- Ensure compatibility with current dependencies
- Test thoroughly before submission

---
*Note: This is a simplified analysis. The AI will provide more specific details during implementation.*""" 