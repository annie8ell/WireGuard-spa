# WireGuard SPA

A complete infrastructure-as-code solution for deploying a WireGuard VPN service with Azure Static Web Apps and Azure Functions.

## Overview

This project provides:
- **Frontend SPA** (Vue.js) with Google and Microsoft authentication
- **Azure Functions Backend** with Durable Functions for orchestrating ephemeral VM lifecycle
- **Bicep Infrastructure Templates** for complete Azure resource provisioning
- **CI/CD Pipeline** for automated infrastructure deployment and code releases

## Architecture

The solution uses:
- **Azure Static Web App** for hosting the SPA with built-in authentication
- **Azure Functions** (Python, Consumption Plan) with Durable Functions for VM orchestration
- **Azure VMs** for WireGuard instances (default mode; ACI is optional but not recommended due to TUN/kernel requirements)
- **System-assigned Managed Identity** with RBAC for secure VM provisioning
- **Application Insights** for monitoring and logging

## Key Features

- **Zero-trust authentication**: Both Google and Microsoft sign-in options
- **Ephemeral VMs**: Temporary WireGuard instances that auto-destroy after session expiry
- **Infrastructure as Code**: Complete Bicep templates for reproducible deployments
- **Automated CI/CD**: Single workflow to provision infrastructure and deploy code
- **Secure by default**: Managed identities, RBAC, HTTPS-only
- **Dry-run mode**: Test orchestration without creating actual VMs

## Prerequisites

1. **Azure Subscription** with permissions to create resources and assign roles
2. **GitHub Repository Secrets**:
   - `AZURE_CREDENTIALS` - Service Principal JSON for infrastructure provisioning
   - `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` - Function App publish profile (optional; can be retrieved dynamically)

### Creating the AZURE_CREDENTIALS Secret

1. Create a Service Principal with Contributor access:
```bash
az ad sp create-for-rbac \
  --name "wireguard-spa-sp" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/{resource-group-name} \
  --sdk-auth
```

2. Copy the JSON output and add it as a GitHub secret named `AZURE_CREDENTIALS`:
```json
{
  "clientId": "<client-id>",
  "clientSecret": "<client-secret>",
  "subscriptionId": "<subscription-id>",
  "tenantId": "<tenant-id>",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

Note: If you prefer subscription-level permissions, use `/subscriptions/{subscription-id}` as the scope.

## Infrastructure

### Bicep Templates (`infra/main.bicep`)

The main Bicep template creates:

1. **Storage Account** - For Azure Functions runtime
2. **Application Insights** - Monitoring and telemetry
3. **Function App** (Linux Consumption, Python 3.9)
   - System-assigned Managed Identity
   - App Settings for runtime, allowed emails, dry-run mode
4. **Static Web App** - Hosts the SPA (Free or Standard SKU)
5. **Role Assignments**:
   - Virtual Machine Contributor (at resource group scope)
   - Network Contributor (at resource group scope)

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `location` | string | `resourceGroup().location` | Azure region |
| `projectName` | string | (required) | Short prefix for resource names |
| `swaSku` | string | `Free` | Static Web App SKU (Free or Standard) |
| `functionRuntimeVersion` | int | `4` | Azure Functions runtime version |
| `allowedEmails` | string | `awwsawws@gmail.com,awwsawws@hotmail.com` | Comma-separated email list |
| `dryRun` | string | `false` | Enable dry-run mode |

### Outputs

- `functionAppName` - Name of the Function App
- `functionAppHostName` - Hostname of the Function App
- `staticWebAppName` - Name of the Static Web App
- `staticWebAppResourceId` - Resource ID of the Static Web App
- `staticWebAppDefaultHostName` - Default hostname of the Static Web App

## Deployment

### Option 1: Automated Deployment (Recommended)

Run the **Provision Infrastructure and Deploy** workflow:

1. Go to **Actions** → **Provision Infrastructure and Deploy**
2. Click **Run workflow**
3. Provide inputs:
   - `resourceGroupName` (default: `wireguard-spa-rg`)
   - `location` (default: `eastus`)
   - `projectName` (default: `wgspa`)
4. Click **Run workflow**

The workflow will:
- Create the resource group (if needed)
- Deploy Bicep templates
- Retrieve the SWA deployment token dynamically
- Deploy the Azure Functions backend
- Build and deploy the SPA frontend

### Option 2: Manual Deployment

1. **Provision Infrastructure**:
```bash
# Create resource group
az group create --name wireguard-spa-rg --location eastus

# Deploy Bicep template
az deployment group create \
  --resource-group wireguard-spa-rg \
  --template-file infra/main.bicep \
  --parameters projectName=wgspa
```

2. **Deploy Backend**:
```bash
cd backend
pip install -r requirements.txt
func azure functionapp publish <function-app-name>
```

3. **Deploy Frontend**:
```bash
cd frontend
npm install
npm run build

# Deploy to Static Web App
az staticwebapp deploy \
  --name <swa-name> \
  --resource-group wireguard-spa-rg \
  --app-location frontend \
  --output-location dist
```

## Post-Deployment Configuration

### 1. Link Function App as Backend API

In the Azure Portal:
1. Navigate to your Static Web App
2. Go to **Backends** blade
3. Add a new backend:
   - **Backend resource type**: Function App
   - **Subscription**: (your subscription)
   - **Resource**: (select your Function App)
   - **Backend name**: `api`
4. Click **Link**

### 2. Configure Authentication Providers

For Google and Microsoft login to work:
1. Navigate to your Static Web App → **Authentication**
2. Configure **Google** provider (optional):
   - Register app in Google Cloud Console
   - Add Client ID and Secret
3. Configure **Azure Active Directory** provider:
   - Use App Registration or Easy Auth
   - Allow accounts in your organization

### 3. Update Allowed Emails

To change authorized users:
- Update the `ALLOWED_EMAILS` environment variable in the Function App settings, or
- Re-deploy infrastructure with `--parameters allowedEmails="user1@example.com,user2@example.com"`

## Backend Mode

The backend supports two modes (controlled by `BACKEND_MODE` environment variable):

### VM Mode (Default, Recommended)
- Creates ephemeral Azure VMs for WireGuard
- Full kernel access, TUN device support
- Best for production WireGuard workloads
- Requires VM and Network Contributor roles

### ACI Mode (Experimental)
- Uses Azure Container Instances
- Faster provisioning but lacks TUN device support
- WireGuard requires kernel modules not available in standard ACI
- Set `BACKEND_MODE=aci` to enable (not recommended)

**Note**: WireGuard typically requires TUN/kernel capabilities not available in Azure Container Instances. We default to VM provisioning for reliable WireGuard operation.

## Development

### Local Development - Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Update local.settings.json with your values
code local.settings.json

# Run Functions locally
func start
```

### Local Development - Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Project Structure

```
WireGuard-spa/
├── infra/
│   └── main.bicep                 # Infrastructure template
├── backend/
│   ├── host.json                  # Functions host config
│   ├── requirements.txt           # Python dependencies
│   ├── local.settings.json        # Local settings
│   ├── shared/                    # Shared utilities
│   │   ├── config.py              # Configuration management
│   │   ├── auth.py                # Authentication helpers
│   │   └── vm_manager.py          # Azure VM lifecycle
│   ├── StartSession/              # HTTP trigger to start session
│   ├── GetStatus/                 # HTTP trigger to get status
│   ├── WireGuardOrchestrator/     # Durable orchestrator
│   ├── ProvisionVM/               # Activity: provision VM
│   └── DestroyVM/                 # Activity: destroy VM
├── frontend/
│   ├── package.json               # NPM dependencies
│   ├── vite.config.js             # Vite config
│   ├── index.html                 # HTML entry point
│   ├── src/
│   │   ├── main.js                # Vue app entry
│   │   └── App.vue                # Main Vue component
│   └── public/
│       └── staticwebapp.config.json  # SWA configuration
└── .github/
    └── workflows/
        └── infra-provision-and-deploy.yml  # CI/CD workflow
```

## Troubleshooting

### Function App Deployment Issues
- Verify `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` secret is set (if not using dynamic retrieval)
- Check Function App logs in Application Insights
- Ensure Python version matches (3.9)

### SWA Deployment Issues
- Verify the SWA deployment token is valid
- Check build output location matches `dist`
- Review workflow logs for build errors

### Authentication Issues
- Ensure users are in the `ALLOWED_EMAILS` list
- Verify authentication providers are configured in SWA
- Check browser console for errors

### VM Provisioning Issues
- Verify Managed Identity has VM and Network Contributor roles
- Check Function App logs for detailed errors
- Try dry-run mode first: set `DRY_RUN=true` in Function App settings

## Security Considerations

- **Secrets**: Never commit secrets to source control
- **Managed Identity**: Function App uses system-assigned identity for Azure API calls
- **RBAC**: Least-privilege role assignments at resource group scope
- **HTTPS**: All traffic uses HTTPS
- **Authentication**: SWA built-in auth with provider integration
- **Authorization**: Allowed emails list enforced in backend

## Cost Optimization

- **Consumption Plan**: Pay only for Function execution time
- **Free SWA Tier**: No cost for the Static Web App (upgrade to Standard for custom domains)
- **Ephemeral VMs**: VMs are destroyed after session expiry to minimize compute costs
- **B1s VM Size**: Smallest size for cost efficiency (configurable)

## Allowed Users

By default, the following users are authorized:
- awwsawws@gmail.com
- awwsawws@hotmail.com

To change, update the `allowedEmails` parameter when deploying infrastructure or modify the `ALLOWED_EMAILS` app setting.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## License

MIT License - See LICENSE file for details