# Changelog

All notable changes to the WireGuard SPA project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-16

### Added - Infrastructure
- Complete Bicep template (`infra/main.bicep`) for Azure resource provisioning
- Storage Account for Azure Functions runtime
- Application Insights for monitoring and telemetry
- Azure Function App (Linux Consumption Plan, Python 3.9)
- System-assigned Managed Identity for Function App
- RBAC role assignments (Virtual Machine Contributor, Network Contributor)
- Azure Static Web App (Free tier) for frontend hosting
- Parameterized configuration with sensible defaults

### Added - Backend (Azure Functions)
- `StartSession` HTTP trigger function (POST /api/start)
- `GetStatus` HTTP trigger function (GET /api/status)
- `WireGuardOrchestrator` Durable Functions orchestrator
- `ProvisionVM` activity function for VM creation
- `DestroyVM` activity function for VM cleanup
- Shared utilities module:
  - Configuration management (`shared/config.py`)
  - Authentication and authorization (`shared/auth.py`)
  - Azure VM lifecycle management (`shared/vm_manager.py`)
- Default allowed users configuration (awwsawws@gmail.com, awwsawws@hotmail.com)
- Dry-run mode for testing without creating actual resources
- Backend mode selection (VM/ACI)

### Added - Frontend (Vue.js SPA)
- Vue.js 3 Single Page Application
- Modern, responsive UI with gradient design
- Google OAuth authentication button
- Microsoft (Azure AD) authentication button
- Session management interface
- Real-time status monitoring with 5-second polling
- Session countdown timer
- Static Web Apps configuration (`staticwebapp.config.json`)
- Vite build configuration

### Added - CI/CD (GitHub Actions)
- `infra-provision-and-deploy.yml` - Main deployment workflow
  - Creates Azure resource group
  - Deploys Bicep infrastructure templates
  - Deploys Azure Functions backend
  - Builds and deploys Static Web App frontend
  - Dynamically retrieves SWA deployment token
- `deploy-backend.yml` - Backend-only deployment workflow
- `deploy-frontend.yml` - Frontend-only deployment workflow
- Workflow inputs for customizable deployments

### Added - Documentation
- Comprehensive `README.md` with project overview
- `QUICKSTART.md` with 15-minute deployment guide
- `SETUP.md` with detailed setup instructions
- `ARCHITECTURE.md` with system design and flow diagrams
- `CONTRIBUTING.md` with contribution guidelines
- `backend/README.md` with Azure Functions documentation
- `frontend/README.md` with Vue.js SPA documentation
- Pull request template
- `LICENSE` (MIT)
- `.gitignore` for build artifacts and dependencies

### Security
- HTTPS-only configuration for all services
- System-assigned Managed Identity (no credentials in code)
- Least-privilege RBAC role assignments
- Email-based authorization whitelist
- OAuth 2.0 authentication via Azure Static Web Apps
- No secrets committed to source control

### Validated
- Bicep template syntax validation
- Python code syntax validation
- YAML workflow syntax validation
- JSON configuration validation

### Notes
- Default backend mode is VM (recommended for WireGuard due to TUN requirements)
- ACI mode available but not recommended for production WireGuard workloads
- All resources created with parameterized naming for flexibility
- Cost-optimized with Consumption plan and ephemeral VMs
- Conducted review of entire code base.

## [Unreleased]

### Planned Features
- WireGuard configuration generation and distribution
- Session extension capability
- Multiple simultaneous sessions per user
- Admin panel for user management
- Session history and analytics
- QR code generation for WireGuard configs
- Multi-region deployment support
- Custom VM size selection
- Azure Key Vault integration for secrets
- Enhanced monitoring and alerting

---

## Release Notes Format

### Added
For new features.

### Changed
For changes in existing functionality.

### Deprecated
For soon-to-be removed features.

### Removed
For now removed features.

### Fixed
For any bug fixes.

### Security
In case of vulnerabilities.
