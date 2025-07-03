# Autonomous GitHub Issue Resolution System - Development Progress

## Project Overview
An autonomous tool that picks GitHub issues, uses Claude Code CLI to work on them, and creates PRs automatically with human oversight.

## System Architecture

### Core Workflow (v1 - Event-Driven)
1. **Issue Discovery**: GitHub webhooks trigger instantly when labels are added/removed
2. **AI Analysis**: Claude Code CLI analyzes issue and proposes solution 
3. **Human Review Loop**: Human reviews/approves AI proposal via GitHub labels
4. **Implementation**: AI implements approved solution (triggered by webhook)
5. **Git Workflow**: Auto-commit, branch creation, PR submission, and issue closure

## Version Planning

### v0 - MVP (Completed ✅)
**Scope**: Simple single-threaded approach with scheduler-based polling
- ✅ Single chat session for all issues (process one issue at a time)
- ✅ Basic GitHub integration (issue fetching, commenting, labeling)
- ✅ Simple human approval workflow
- ✅ Basic git operations (commit, branch, push, PR)
- ✅ Configuration via settings file
- ✅ Scheduler-based issue polling
- ✅ Complete end-to-end workflow with automatic issue closure

**Key Decisions for v0**:
- ✅ Process issues sequentially (no parallel processing)
- ✅ Single Claude Code CLI chat session
- ✅ Wait for current issue completion before picking next
- ✅ Simple label-based approval system
- ✅ Polling-based issue detection

### v1 - Event-Driven Architecture (Current Target 🔄)
**Major Upgrade**: Replace polling with real-time webhooks
- **🔄 GitHub Webhooks Integration**: Real-time event-driven processing
  - Replace scheduler polling with instant webhook triggers
  - Process issues immediately when labels are added/removed
  - Webhook signature verification for security
  - Background task processing for async handling
- **🔄 System Cleanup**: Remove scheduler-related components
  - Remove SchedulerService and scheduler router
  - Keep manual trigger endpoints for testing/debugging
  - Streamline codebase and reduce complexity
- **🔄 Enhanced Performance**: Instant response times
  - No more 1-10 minute delays from polling
  - Immediate processing when `ai-ready` label added
  - Instant implementation when `ai-approved` label added
- **🔄 Production Readiness**: Improved reliability and efficiency
  - Reduced API calls (no unnecessary polling)
  - Better resource utilization
  - Webhook retry handling via GitHub's built-in mechanism

**Future v1 Enhancements**:
- [ ] **Separate Chat Threads**: Each issue gets its own isolated Claude Code chat session
- [ ] **Parallel Processing**: Handle multiple issues simultaneously
- [ ] **Enhanced Error Handling**: Robust fallback mechanisms
- [ ] **Metrics & Monitoring**: Track success rates, processing times

### v2 - Advanced Features
**Future Considerations**:
- [ ] **Automated Testing**: Run tests before creating PR
- [ ] **Multi-repo Support**: Handle issues across multiple repositories
- [ ] **Smart Issue Prioritization**: AI-driven issue selection
- [ ] **Integration with CI/CD**: Automated deployment pipeline
- [ ] **Advanced Human Review**: Web interface for proposal review

## Current Development Status

### Completed
- [x] **Docker Compose & Deployment** ✅ (Latest Update)
  - [x] Created Docker Compose setup for easy deployment on any machine
  - [x] Added comprehensive deployment guide (DEPLOYMENT.md)
  - [x] Configured environment variable management via .env files
  - [x] Set up health checks and monitoring for containers
  - [x] Added production-ready deployment configuration
- [x] **Docker & CI/CD Pipeline** ✅
  - [x] Created GitHub Actions workflow for automated builds
  - [x] Implemented automatic semantic versioning with tags (sentinel-v*)
  - [x] Set up GitHub Container Registry publishing (ghcr.io/dhrupadsah/sentinel-system)
  - [x] Created optimized Dockerfile with PDM support
  - [x] Added .dockerignore for efficient builds
  - [x] Configured workflow triggers for main branch and manual dispatch
- [x] **AI Integration Migration** ✅
  - [x] Migrated from Gemini CLI to Aider CLI with Claude Sonnet 4
  - [x] Updated all service references and imports  
  - [x] Updated configuration settings (ANTHROPIC_API_KEY)
  - [x] Updated documentation and examples
  - [x] Verified Aider CLI integration working
- [x] **AI Analysis Output Improvement** ✅
  - [x] Implemented clean, professional analysis format
  - [x] Added technical noise filtering and output processing
  - [x] Created structured proposal templates with emoji headers
  - [x] Added fallback formatting for edge cases
  - [x] Updated all documentation to reflect new format
- [x] Project architecture design
- [x] Development roadmap creation
- [x] PDM project setup with dependencies
- [x] FastAPI application structure
- [x] Configuration management (Pydantic Settings)
- [x] API router structure (health, github, scheduler)
- [x] GitHub service implementation
- [x] Health check endpoints
- [x] Environment configuration example
- [x] Comprehensive README documentation
- [x] Claude Code CLI service implementation (using authenticated CLI)
- [x] Issue processor service (complete workflow orchestration)
- [x] Git service implementation (branch management, commits, pushes)
- [x] Scheduler service implementation (automated processing)
- [x] Updated health checks with service integration

### In Progress - v1 Webhook Implementation
- [x] Testing and validation of complete workflow
- [x] Error handling improvements (git stashing, phase separation)
- [x] Fixed premature code implementation during analysis phase
- [x] Automatic issue closure after PR creation
- [x] **GitHub Webhooks Integration** ✅
  - [x] Create webhook endpoint with signature verification
  - [x] Implement label-based event filtering
  - [x] Add background task processing for async handling
  - [x] Handle `issues.labeled` and `issues.unlabeled` events
  - [x] Add webhook test endpoint for debugging
- [x] **System Cleanup** ✅
  - [x] Remove SchedulerService and related components
  - [x] Remove scheduler router and endpoints
  - [x] Update configuration to remove scheduler settings
  - [x] Clean up imports and dependencies
- [ ] **Documentation Updates** 🔄
  - [ ] Update README with webhook setup instructions
  - [ ] Add webhook configuration examples
  - [ ] Document GitHub webhook setup process

### Completed - GitHub App Migration ✅
**Goal**: Transform from single-repo service to centralized multi-repo GitHub App
- [x] **Authentication Migration** ✅
  - [x] Implement GitHub App authentication service
  - [x] Add JWT token generation for GitHub App
  - [x] Add installation token management
  - [x] Update health checks to support GitHub App authentication
- [x] **Multi-Repository Support** ✅
  - [x] Update webhook handler to support multiple repositories
  - [x] Add repository validation and filtering
  - [x] Update configuration to support both legacy and GitHub App modes
  - [x] Add repository discovery from GitHub App installation
- [x] **Configuration Updates** ✅
  - [x] Add GitHub App configuration alongside legacy PAT config
  - [x] Update environment variables for App credentials
  - [x] Update env.example with GitHub App settings
  - [x] Maintain backward compatibility with legacy mode

### Next Priority - GitHub App Setup & Testing 🔄
**Goal**: Complete GitHub App setup and test the multi-repo functionality
- [x] **GitHub App Creation & Setup** ✅
  - [x] Create GitHub App with required permissions
  - [x] Configure webhook endpoint for GitHub App
  - [x] Generate and secure private key for authentication
  - [x] Install GitHub App on target organization
  - [x] Fix timezone issue in JWT token generation
  - [x] Verify GitHub App authentication working (30 repositories accessible)
- [x] **Issue Processor Multi-Repo Support** ✅
  - [x] Update IssueProcessor.process_issue() to accept repository parameter
  - [x] Add repository context to log messages
  - [x] Fix argument mismatch error in webhook processing
- [x] **Service Updates for Multi-Repo** ✅
  - [x] Update GitHubService to use GitHub App authentication
  - [x] Add repository parameter to all GitHubService methods
  - [x] Update GitService to handle repository-specific operations
  - [x] Update ClaudeService to work with repository context
  - [x] Create WorkspaceService for repository cloning and cleanup
  - [x] Update IssueProcessor to use multi-repository workflow

### Remaining Tasks - Complete GitHub App Implementation 🎯

#### Critical - Service Layer Updates ✅ (COMPLETED)
- [x] **GitHubService Multi-Repo Support** ✅
  - [x] Add repository parameter to all methods (get_issue, add_comment, add_label, etc.)
  - [x] Switch from Personal Access Token to GitHub App authentication
  - [x] Update API calls to use installation tokens instead of PAT
  - [x] Maintain backward compatibility with legacy single-repo mode

- [x] **GitService Repository Context** ✅
  - [x] Add repository parameter to GitService methods
  - [x] Handle repository cloning/switching for multi-repo operations
  - [x] Update git operations to work with different repository contexts
  - [x] Implement repository isolation with workspace directories

- [x] **ClaudeService Repository Awareness** ✅
  - [x] Update Claude CLI commands to work with repository context
  - [x] Ensure Claude operates in correct repository directory
  - [x] Add repository information to Claude prompts for better context

- [x] **WorkspaceService Implementation** ✅
  - [x] Create workspace management for Docker environments
  - [x] Implement repository cloning with authentication
  - [x] Add automatic workspace cleanup
  - [x] Support context manager for safe operations

#### Medium Priority - API & Configuration Updates
- [ ] **GitHub Router Updates** 🔄
  - [ ] Update GitHub API endpoints to support repository parameter
  - [ ] Add multi-repository issue listing endpoints
  - [ ] Update manual processing endpoints for repository context

- [ ] **Configuration Cleanup** 🔄
  - [ ] Deprecate legacy GITHUB_REPO and GITHUB_TOKEN settings
  - [ ] Add migration warnings for legacy configuration
  - [ ] Update configuration validation

#### Low Priority - Documentation & Testing
- [ ] **Documentation Updates** 🔄
  - [ ] Update README with GitHub App setup instructions
  - [ ] Add multi-repository usage examples
  - [ ] Document migration from PAT to GitHub App
  - [ ] Update API documentation for repository parameters

- [ ] **End-to-End Testing** 🔄
  - [ ] Test complete workflow across multiple repositories
  - [ ] Verify webhook processing for different repos
  - [ ] Test error handling and fallback scenarios
  - [ ] Performance testing with multiple concurrent issues

#### Production Readiness
- [ ] **Security & Monitoring** 🔄
  - [ ] Re-enable webhook signature verification
  - [ ] Add rate limiting for GitHub API calls
  - [ ] Implement proper error tracking and alerting
  - [ ] Add metrics for multi-repository operations

- [ ] **Deployment Updates** 🔄
  - [ ] Update Docker configuration for GitHub App mode
  - [ ] Add GitHub App private key handling in deployment
  - [ ] Update deployment documentation

### Current Status - Implementation Complete! 🎉
**ALL CRITICAL COMPONENTS IMPLEMENTED**:
1. ✅ **GitHubService Authentication** - Now uses GitHub App tokens with multi-repo support
2. ✅ **Repository Context** - All services are repository-aware
3. ✅ **Git Operations** - Handle multiple repository contexts with workspace isolation
4. ✅ **Workspace Management** - Docker-ready with automatic clone/cleanup
5. ✅ **Claude Integration** - Repository-aware with proper working directories

### Next Immediate Steps (Testing & Polish)
1. **Test Multi-Repo Workflow** - End-to-end testing across repositories
2. **Fix any integration issues** - Debug and resolve any remaining bugs
3. **Update API endpoints** - Make GitHub router multi-repo aware
4. **Documentation** - Update setup and usage guides
5. **Production deployment** - Test in Docker environment

### Next Steps
1. ✅ ~~Set up project structure~~
2. ✅ ~~Implement GitHub API integration~~
3. ✅ ~~Complete Claude Code CLI integration service~~
4. ✅ ~~Create basic issue processing workflow~~
5. ✅ ~~Implement scheduler service~~
6. ✅ ~~Add git operations service~~
7. ✅ ~~Set up Docker containerization and CI/CD pipeline~~
8. ✅ ~~Create Docker Compose deployment setup~~
9. 🔄 Testing and refinement
10. 🔄 Create environment file and configure settings
11. 🔄 Test complete end-to-end workflow
12. 🔄 Add monitoring and logging improvements
13. 🔄 Production deployment and testing

## Technical Decisions

### GitHub Integration (v1 - Webhook-Driven)
- **GitHub Webhooks**: Real-time event processing for instant responses
- **GitHub REST API**: For issue management, commenting, and labeling
- **Webhook Events**: Listen for `issues.labeled` and `issues.unlabeled` events
- **Security**: Webhook signature verification using GitHub secret
- **Labels for workflow state management**:
  - `sentinel-analyze` - Issues ready for AI analysis (triggers analysis)
  - `proposal-pending` - AI has proposed solution, awaiting human review
  - `approved` - Human has approved AI's proposal (triggers implementation)
  - `implementing` - AI is currently implementing solution

### Event Processing Architecture
- **Async Processing**: Background tasks for webhook event handling
- **Quick Response**: Return 200 OK immediately to prevent GitHub retries
- **Idempotent Processing**: Handle duplicate webhooks gracefully
- **Error Handling**: Robust error recovery with GitHub's built-in retry mechanism

### AI Integration
- Claude Code CLI already configured in target repository
- No git cloning needed (works within existing repo)
- AI adds comments to issues for transparency
- Background task processing prevents blocking webhook responses

### Human Review Process
- AI posts proposal as GitHub issue comment
- Human reviews and either approves or requests changes via labels
- Webhook instantly triggers next phase when approval label added
- Iterative refinement until approval received

## Configuration Requirements
- Target repository settings
- GitHub API credentials
- Issue label configurations
- Claude Code CLI setup verification
- Scheduling parameters
- Docker deployment environment
- GitHub Container Registry access

## Risk Mitigation
- Human approval required before any code changes
- All AI actions logged as GitHub comments
- Git branch isolation for each issue
- Rollback capabilities

---

*Last Updated: December 2024*
*Version: v1 Implementation Phase - Webhook Integration* 