# GitHub Copilot Instructions for WireGuard-spa

This repository contains a WireGuard on-demand launcher built with a Vue.js frontend, Python Azure Functions backend, and Bicep infrastructure templates.

## Project Overview

This is a full-stack application that provisions on-demand WireGuard VPN servers on Azure:

- **Frontend**: Vue.js SPA (in `/frontend`) using Vite for build
- **Backend**: Python 3.10 Azure Durable Functions (in `/backend`)
- **Infrastructure**: Bicep templates (in `/infra`) for Azure resource provisioning
- **Deployment**: GitHub Actions workflows for CI/CD

## Architecture

### Frontend (Vue.js SPA)
- Location: `/frontend`
- Framework: Vue 3 with Vite
- Authentication: Azure Static Web Apps built-in auth (Google/Microsoft)
- Build commands: `npm run dev` (development), `npm run build` (production)

### Backend (Azure Durable Functions)
- Location: `/backend`
- Runtime: Python 3.10
- Pattern: Durable Functions orchestrator with activities
- Authentication: Validates X-MS-CLIENT-PRINCIPAL header against allowlist
- Key modules:
  - `/backend/functions/StartSession/` - HTTP trigger to start orchestration
  - `/backend/functions/WireGuardOrchestrator/` - Main orchestration logic
  - `/backend/functions/ProvisionVM/` - Activity to provision VM
  - `/backend/functions/DestroyVM/` - Activity to destroy VM
  - `/backend/functions/GetStatus/` - HTTP trigger for status checks
  - `/backend/shared/` - Shared utilities (auth, wireguard config)

### Infrastructure
- Location: `/infra`
- Technology: Azure Bicep
- Provisions: Static Web App, Function App, Storage Account, and supporting resources

## Coding Standards

### Python (Backend)
- Follow PEP 8 style guide
- Use type hints where applicable
- Add docstrings to functions and classes
- Keep functions focused and small
- Handle errors gracefully with appropriate logging
- Use Azure SDK best practices (managed identity, async operations)

### JavaScript/Vue (Frontend)
- Use ES6+ modern JavaScript features
- Follow Vue.js 3 Composition API style guide
- Use meaningful component and variable names
- Keep components small and focused
- Use Vite for development and building

### Bicep (Infrastructure)
- Use descriptive resource names
- Add comments for complex logic
- Use parameters for configurable values
- Include output values for important resources
- Follow Azure naming conventions

## Development Workflow

### Backend Development
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp local.settings.json.template local.settings.json
# Edit local.settings.json with your values
func start
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev      # Development server
npm run build    # Production build
```

### Testing
- Python: Run tests with `python -m pytest tests/` from `/backend`
- Frontend: Run tests with `npm test` from `/frontend`
- Infrastructure: Validate with `az bicep build --file infra/main.bicep`

## Important Configuration

### Environment Variables (Backend)
- `AZURE_SUBSCRIPTION_ID` - Azure subscription ID
- `AZURE_RESOURCE_GROUP` - Resource group for VM provisioning
- `ADMIN_USERNAME` - Default admin username for VMs
- `ALLOWED_EMAILS` - Comma-separated list of authorized emails
- `DRY_RUN` - Set to "true" for testing without creating real VMs

### DRY_RUN Mode
The backend supports DRY_RUN mode which simulates VM provisioning without actually creating Azure resources. This is useful for testing and development. When DRY_RUN=true:
- No actual VMs are created
- Returns sample WireGuard configuration
- Still creates orchestration and timer
- Logs teardown actions without deleting resources

## Security Considerations

- Authentication is handled by Azure Static Web Apps
- Authorization uses email allowlist (ALLOWED_EMAILS)
- Backend validates X-MS-CLIENT-PRINCIPAL header
- Use Managed Identity for Azure resource access (preferred over service principals)
- Never commit secrets or credentials to the repository
- VMs auto-delete after 30 minutes (configurable timeout)

## File Structure

```
.
├── .github/
│   ├── workflows/          # GitHub Actions CI/CD workflows
│   └── copilot-instructions.md
├── backend/
│   ├── functions/          # Azure Functions (HTTP triggers, activities)
│   ├── shared/             # Shared utilities
│   ├── requirements.txt    # Python dependencies
│   └── host.json           # Function App configuration
├── frontend/
│   ├── src/                # Vue.js source code
│   ├── public/             # Static assets
│   ├── package.json        # NPM dependencies
│   └── vite.config.js      # Vite configuration
├── infra/
│   └── main.bicep          # Azure infrastructure template
└── scripts/                # Helper scripts

```

## Common Tasks

### Adding a New Backend Function
1. Create a new directory under `/backend/functions/`
2. Add `function.json` with bindings configuration
3. Add `__init__.py` with function implementation
4. Follow Azure Functions best practices for Durable Functions
5. Update orchestrator if needed

### Modifying Frontend Components
1. Components are in `/frontend/src/`
2. Use Vue 3 Composition API
3. Follow existing patterns for state management
4. Test in development mode before building

### Updating Infrastructure
1. Modify Bicep templates in `/infra/`
2. Validate with `az bicep build`
3. Test with `az deployment group what-if`
4. Follow Azure resource naming conventions

## Deployment

- Frontend: Deployed to Azure Static Web Apps via GitHub Actions
- Backend: Deployed to Azure Functions via GitHub Actions
- Infrastructure: Provisioned via Bicep templates in GitHub Actions
- All workflows are in `.github/workflows/`

## When Making Changes

1. **Understand the context**: Review relevant documentation (README, ARCHITECTURE, CONTRIBUTING)
2. **Follow conventions**: Match existing code style and patterns
3. **Test locally**: Use DRY_RUN mode for backend, dev server for frontend
4. **Update documentation**: Update README or other docs if functionality changes
5. **Security first**: Never expose credentials or lower security barriers
6. **Minimal changes**: Make surgical, focused changes that address the specific issue

## Key Dependencies

### Backend
- `azure-functions-durable` - Durable Functions SDK
- `azure-identity` - Authentication with Azure services
- `azure-mgmt-compute` - VM management
- `azure-mgmt-network` - Network resource management
- `paramiko` - SSH operations
- `cryptography` - Key generation and encryption

### Frontend
- `vue` - Vue.js framework
- `vite` - Build tool and dev server
- `@vitejs/plugin-vue` - Vite Vue plugin

## Additional Resources

- [Azure Durable Functions Documentation](https://docs.microsoft.com/azure/azure-functions/durable/)
- [Azure Static Web Apps Documentation](https://docs.microsoft.com/azure/static-web-apps/)
- [Vue.js Documentation](https://vuejs.org/)
- [WireGuard Documentation](https://www.wireguard.com/)
- Project documentation in `/README.md`, `/ARCHITECTURE.md`, `/CONTRIBUTING.md`
