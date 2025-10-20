# GitHub Copilot Instructions for WireGuard-spa

This repository contains a WireGuard on-demand launcher built with a zero-build SPA frontend and Azure Static Web Apps built-in Functions backend (Python 3.11).

> **📝 Migration Note**: This project has migrated from Azure Durable Functions to Azure Static Web Apps built-in Functions. See [MIGRATION.md](MIGRATION.md) for details.

## Project Overview

This is a full-stack application that provisions on-demand WireGuard VPN servers on Azure:

- **Frontend**: Zero-build SPA using Alpine.js and Foundation CSS (via CDN)
- **Backend**: Python 3.11 Azure Static Web Apps built-in Functions (in `/api`)
- **Legacy Code**: `/backend` contains old Durable Functions code (not deployed, kept for reference)
- **Infrastructure**: Bicep templates (in `/infra`) for Azure resource provisioning
- **Deployment**: Single GitHub Actions workflow for SWA deployment

## Architecture

### Frontend (Zero-build SPA)
- Location: `/index.html` (root) with optional Vue.js build in `/frontend`
- Technology: Zero-build SPA using Alpine.js and Foundation CSS via CDN
- Authentication: Azure Static Web Apps built-in auth (Google/Microsoft)
- Authorization: Role-based access using SWA's 'invited' role
- No build step required for main SPA

### Backend (Azure Static Web Apps Functions)
- Location: `/api`
- Runtime: Python 3.11
- Pattern: 202 Accepted + status polling (pass-through architecture)
- Authentication: Validates X-MS-CLIENT-PRINCIPAL header for 'invited' role
- Key endpoints:
  - `POST /api/start_job` - Creates or returns existing WireGuard VM (idempotent)
  - `GET /api/job_status?id={operationId}` - Queries Azure for VM status
- Key modules:
  - `/api/start_job/` - HTTP trigger for job creation
  - `/api/job_status/` - HTTP trigger for status queries
  - `/api/shared/auth.py` - User validation and role checking
  - `/api/shared/vm_provisioner.py` - Direct Azure VM provisioning via Azure SDK

### Legacy Code (Not Deployed)
- Location: `/backend`
- Contains old Durable Functions implementation
- Kept for reference only - DO NOT modify or use for new features
- Current deployment uses `/api` directory only

### Infrastructure
- Location: `/infra`
- Technology: Azure Bicep
- Provisions: Single Azure Static Web App resource (includes built-in Functions runtime)
- No separate Function App or Storage Account needed

## Coding Standards

### Python (SWA Functions in /api)
- Follow PEP 8 style guide
- Use type hints where applicable
- Add docstrings to functions and classes
- Keep functions focused and small
- Handle errors gracefully with appropriate logging
- Use Azure SDK for direct VM provisioning (Service Principal authentication)
- Functions must be stateless (no Durable Functions state management)
- Use 202 Accepted pattern for async operations

### JavaScript/Alpine.js (Frontend)
- Zero-build SPA uses Alpine.js via CDN (no compilation required)
- Follow Alpine.js conventions for x-data, x-on, x-show directives
- Keep JavaScript minimal and inline in HTML
- Foundation CSS for styling via CDN
- Optional Vue.js build available in `/frontend` for more complex UI needs

### Bicep (Infrastructure)
- Use descriptive resource names
- Add comments for complex logic
- Use parameters for configurable values
- Include output values for important resources
- Follow Azure naming conventions
- Focus on single SWA resource (no separate Function App needed)

## Development Workflow

### API Development (SWA Functions)
```bash
cd api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run locally with Azure Functions Core Tools
func start
```

### Frontend Development
The main SPA (`index.html` at root) requires no build step:
```bash
# Serve with any static web server
python -m http.server 8000
# Or use Azure SWA CLI for local testing with authentication
```

For the Vue.js build (optional, in `/frontend`):
```bash
cd frontend
npm install
npm run dev      # Development server
npm run build    # Production build
```

### Testing
- API: Test functions locally with `func start` in `/api` directory
- Frontend: Open `index.html` in browser or use local web server
- Infrastructure: Validate with `az bicep build --file infra/main.bicep`

## Important Configuration

### SWA App Settings (Environment Variables)
Configure these in Azure Portal → Static Web App → Configuration:
- `AZURE_SUBSCRIPTION_ID` - Azure subscription ID
- `AZURE_RESOURCE_GROUP` - Resource group for VM provisioning
- `AZURE_CLIENT_ID` - Service Principal application ID
- `AZURE_CLIENT_SECRET` - Service Principal secret
- `AZURE_TENANT_ID` - Azure AD tenant ID
- `DRY_RUN` - Set to "true" for testing without creating real VMs

### DRY_RUN Mode
The API supports DRY_RUN mode which simulates VM provisioning without actually creating Azure resources. When DRY_RUN=true:
- No actual VMs are created
- Returns sample WireGuard configuration
- Useful for testing authentication and UI flow
- Cost-free development and testing

## Security Considerations

- Authentication is handled by Azure Static Web Apps built-in auth
- Authorization uses SWA's role-based system with 'invited' role
- API validates X-MS-CLIENT-PRINCIPAL header and checks for 'invited' role (defense in depth)
- Service Principal credentials for VM provisioning (Managed Identity not supported in SWA Functions)
- Never commit secrets or credentials to the repository
- VMs auto-delete after 30 minutes
- Idempotent design: Only one VM exists at a time per resource group

## File Structure

```
.
├── .github/
│   ├── workflows/
│   │   └── azure-static-web-apps.yml  # Single deployment workflow
│   └── copilot-instructions.md
├── api/                               # SWA built-in Functions (CURRENT)
│   ├── start_job/                     # POST /api/start_job endpoint
│   ├── job_status/                    # GET /api/job_status endpoint
│   ├── shared/
│   │   ├── auth.py                    # User validation and role checking
│   │   └── vm_provisioner.py          # Direct Azure VM provisioning
│   ├── requirements.txt               # Python dependencies
│   └── host.json                      # Functions host configuration
├── backend/                           # LEGACY - Old Durable Functions (NOT DEPLOYED)
│   └── (Do not modify - kept for reference only)
├── frontend/                          # Optional Vue.js build
│   ├── src/                           # Vue.js source code
│   ├── public/                        # Static assets
│   ├── package.json                   # NPM dependencies
│   └── vite.config.js                 # Vite configuration
├── infra/
│   └── main.bicep                     # Azure infrastructure (SWA only)
├── index.html                         # Main zero-build SPA (at root)
├── routes.json                        # SWA routing configuration
├── staticwebapp.config.json           # SWA configuration
└── scripts/                           # Helper scripts
```

## Common Tasks

### Adding a New API Function
1. Create a new directory under `/api/` (e.g., `/api/my_function/`)
2. Add `function.json` with HTTP bindings configuration
3. Add `__init__.py` with function implementation
4. Follow SWA Functions conventions (stateless, HTTP triggers only)
5. Use shared modules in `/api/shared/` for common functionality
6. **DO NOT** modify `/backend` - it's legacy code

### Modifying Frontend
1. Main SPA is `index.html` at root - no build step required
2. Edit inline JavaScript using Alpine.js conventions
3. For complex features, use Vue.js build in `/frontend/src/`
4. Test locally before deploying

### Updating Infrastructure
1. Modify Bicep templates in `/infra/`
2. Focus on SWA resource configuration
3. Validate with `az bicep build --file infra/main.bicep`
4. Test with `az deployment group what-if`

## Deployment

- Single deployment via `.github/workflows/azure-static-web-apps.yml`
- Deploys both frontend (SPA) and API (built-in Functions) together
- No separate Function App deployment needed
- Infrastructure provisioned via Bicep templates in `/infra/`
- Deployment triggered on push to `main` or via `workflow_dispatch`

## When Making Changes

1. **Understand the context**: Review relevant documentation (README, ARCHITECTURE, MIGRATION)
2. **Follow conventions**: Match existing code style and patterns
3. **Know the architecture**: Current implementation uses SWA Functions in `/api`, not Durable Functions
4. **Test locally**: Use DRY_RUN mode for API, open index.html for frontend testing
5. **Update documentation**: Update README or other docs if functionality changes
6. **Security first**: Never expose credentials or lower security barriers
7. **Minimal changes**: Make surgical, focused changes that address the specific issue
8. **Avoid legacy code**: Do not modify `/backend` directory - use `/api` for all API changes

## Key Dependencies

### API (SWA Functions in /api)
- `azure-functions` - Azure Functions SDK
- `azure-identity` - Authentication with Azure services (Service Principal)
- `azure-mgmt-compute` - VM management
- `azure-mgmt-network` - Network resource management
- `requests` - HTTP requests (if needed for external APIs)

### Frontend
- **Zero-build SPA** (index.html): Alpine.js and Foundation CSS via CDN
- **Optional Vue.js build** (frontend/):
  - `vue` - Vue.js framework
  - `vite` - Build tool and dev server
  - `@vitejs/plugin-vue` - Vite Vue plugin

## Additional Resources

- [Azure Static Web Apps Documentation](https://docs.microsoft.com/azure/static-web-apps/)
- [Azure Static Web Apps Functions Documentation](https://docs.microsoft.com/azure/static-web-apps/apis)
- [Alpine.js Documentation](https://alpinejs.dev/)
- [Foundation CSS Documentation](https://get.foundation/)
- [WireGuard Documentation](https://www.wireguard.com/)
- Project documentation in `/README.md`, `/ARCHITECTURE.md`, `/MIGRATION.md`, `/CONTRIBUTING.md`

## Important Notes

- **Current Architecture**: Uses SWA built-in Functions (Python 3.11) in `/api` directory
- **Legacy Code**: `/backend` contains old Durable Functions implementation - DO NOT USE
- **Migration**: See [MIGRATION.md](../MIGRATION.md) for details on the architectural changes
- **Idempotent Design**: Only one WireGuard VM exists at a time; multiple requests return the same VM
- **Pass-through Pattern**: API queries Azure directly for status (no local state beyond in-memory cache)
