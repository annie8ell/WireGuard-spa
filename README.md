# WireGuard On-Demand Launcher

A minimal end-to-end solution for provisioning on-demand WireGuard VPN servers on Azure. This project uses a zero-build SPA frontend with Azure Static Web Apps authentication and a Python-based Azure Durable Functions backend that provisions Ubuntu VMs with WireGuard, then automatically tears them down after 30 minutes.

## Architecture Overview

### Frontend (SPA)
- **Technology**: Zero-build Single Page Application using Foundation CSS and Alpine.js (via CDN)
- **Authentication**: Azure Static Web Apps built-in authentication (Google/Microsoft)
- **Authorization**: Hardcoded allowlist with seed user `annie8ell@gmail.com`
- **Deployment**: Azure Static Web Apps

### Backend (Durable Functions)
- **Technology**: Python 3.10 Azure Durable Functions
- **Pattern**: Async HTTP API with orchestrator
- **Authentication**: Validates X-MS-CLIENT-PRINCIPAL header against allowlist
- **VM**: Minimal Ubuntu VM (Standard_B1ls) with WireGuard
- **Auto-teardown**: 30-minute durable timer

### Why VM instead of ACI?
WireGuard requires kernel-level TUN/TAP device support which Azure Container Instances (ACI) doesn't provide. A lightweight VM is the most straightforward solution for running WireGuard on Azure.

## Features

- ✅ **Zero-build SPA** - No compilation or bundling required
- ✅ **Built-in authentication** - Uses Azure SWA auth (Google/Microsoft)
- ✅ **Email allowlist** - Simple authorization control
- ✅ **DRY_RUN mode** - Test without provisioning Azure resources
- ✅ **Automatic teardown** - VMs automatically deleted after 30 minutes
- ✅ **Minimal cost** - Uses cheapest VM size (Standard_B1ls)
- ✅ **Download config** - WireGuard configuration downloads as `.conf` file
- ✅ **CI/CD ready** - GitHub Actions workflows included

## Prerequisites

### Azure Resources
1. **Azure Subscription** with permissions to create VMs
2. **Azure Static Web App** (Free tier works)
3. **Azure Function App** (Consumption plan, Python 3.10)
4. **Azure Storage Account** (for Durable Functions state)
5. **Resource Group** where VMs will be created

### Required GitHub Secrets
- `AZURE_CREDENTIALS` - Service principal credentials for Azure login (JSON format)

## Setup Instructions

### Quick Start with Infrastructure Workflow

The easiest way to get started is using the automated infrastructure workflow:

1. **Create Azure Service Principal**
   ```bash
   az ad sp create-for-rbac \
     --name wireguard-spa-deployer \
     --role Contributor \
     --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID> \
     --sdk-auth
   ```
   Save the JSON output as the `AZURE_CREDENTIALS` secret in GitHub.

2. **Run the Workflow**
   - Navigate to **Actions** → **Provision Infrastructure and Deploy**
   - Click **Run workflow**
   - Choose location (default: uksouth) and resource group name
   - The workflow will:
     - Create all Azure resources
     - Deploy the Functions backend with DRY_RUN=true
     - Deploy the SPA
     - Configure necessary settings automatically

3. **Verify and Test**
   - Check the workflow summary for deployment details
   - Verify SWA Backends linking in Azure Portal
   - Test with DRY_RUN=true (no actual VMs created)
   - When ready, set DRY_RUN=false via Azure Portal or CLI

### Manual Setup

If you prefer manual setup, follow these steps:

#### 1. Create Azure Resources

##### Create Resource Group
```bash
az group create --name wireguard-rg --location uksouth
```

##### Create Storage Account (for Durable Functions)
```bash
az storage account create \
  --name wireguardstorage123 \
  --resource-group wireguard-rg \
  --location uksouth \
  --sku Standard_LRS
```

##### Create Function App
```bash
az functionapp create \
  --name wireguard-functions \
  --resource-group wireguard-rg \
  --storage-account wireguardstorage123 \
  --consumption-plan-location uksouth \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --os-type Linux
```

##### Create Static Web App
```bash
az staticwebapp create \
  --name wireguard-spa \
  --resource-group wireguard-rg \
  --location uksouth \
  --sku Free
```

#### 2. Configure Function App Permissions

The Function App needs permission to create VMs. Choose one of these options:

##### Option A: Managed Identity (Recommended)
```bash
# Enable system-assigned managed identity
az functionapp identity assign \
  --name wireguard-functions \
  --resource-group wireguard-rg

# Grant Contributor role to the identity
PRINCIPAL_ID=$(az functionapp identity show \
  --name wireguard-functions \
  --resource-group wireguard-rg \
  --query principalId -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role Contributor \
  --scope /subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/wireguard-rg
```

##### Option B: Service Principal
```bash
# Create service principal
az ad sp create-for-rbac \
  --name wireguard-sp \
  --role Contributor \
  --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/wireguard-rg

# Note the output: appId, password, tenant
# Set these as Function App settings: AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
```

#### 3. Configure Function App Settings

Set the required application settings:

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az functionapp config appsettings set \
  --name wireguard-functions \
  --resource-group wireguard-rg \
  --settings \
    AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
    AZURE_RESOURCE_GROUP="wireguard-rg" \
    ADMIN_USERNAME="azureuser" \
    ALLOWED_EMAILS="awwsawws@gmail.com,awwsawws@hotmail.com" \
    DRY_RUN="true"
```

**Note**: Start with `DRY_RUN=true` to test the flow without creating real VMs. The automated workflow sets these automatically.

#### 4. Link Function App as Backend in Static Web App

In Azure Portal:
1. Navigate to your Static Web App
2. Go to **APIs** blade (or **Backends** in newer portal versions)
3. Click **Link** and select your Function App
4. Set the API location to `/api`

#### 5. Configure GitHub Secrets

In your GitHub repository settings (Settings > Secrets and variables > Actions):

**AZURE_CREDENTIALS** (required for infrastructure workflow)
```bash
az ad sp create-for-rbac \
  --name wireguard-spa-deployer \
  --role Contributor \
  --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID> \
  --sdk-auth
```
Add the entire JSON output as a secret named `AZURE_CREDENTIALS`.

#### 6. Configure Authentication in Static Web App

1. In Azure Portal, go to your Static Web App
2. Navigate to **Authentication** (or **Configuration** > **Authentication**)
3. Configure identity providers (Google and/or Microsoft)
4. Set allowed roles and permissions as needed

#### 7. Deploy

**Using the Infrastructure Workflow (Recommended):**
- Navigate to **Actions** → **Provision Infrastructure and Deploy**
- Click **Run workflow** and select your parameters
- The workflow is **manual-only** (no automatic triggers on push)
- It will create all resources, deploy backend and frontend automatically

**Using Individual Workflows (Alternative):**
- The SPA can deploy via `swa-deploy.yml`
- The Functions can deploy via `functions-deploy.yml`

## Usage

### For End Users

1. **Navigate** to your Static Web App URL (e.g., `https://wireguard-spa.azurestaticapps.net`)
2. **Sign in** with Google or Microsoft account (if you're in the allowlist)
3. **Click** "Request VPN" button
4. **Wait** for the provisioning to complete (a few minutes in DRY_RUN mode, longer for real VMs)
5. **Download** the `wireguard.conf` file
6. **Import** into your WireGuard client (mobile or desktop)
7. **Connect** and enjoy your VPN!

The VM will automatically be torn down after 30 minutes.

### Testing with DRY_RUN

When `DRY_RUN=true`, the backend:
- Does NOT create any Azure VMs
- Returns a sample WireGuard configuration immediately
- Still creates the orchestration and 30-minute timer
- Logs teardown actions without actually deleting resources

This is perfect for:
- Testing the UI flow
- Validating authentication and authorization
- Confirming orchestration logic
- Cost-free development

### Switching to Production Mode

Once you've tested with `DRY_RUN=true`, enable real VM provisioning:

**Via Azure Portal:**
1. Navigate to your Function App
2. Go to Configuration → Application Settings
3. Change `DRY_RUN` to `false`
4. Click Save and restart the Function App

**Via Azure CLI:**
```bash
az functionapp config appsettings set \
  --name wireguard-functions \
  --resource-group wireguard-rg \
  --settings DRY_RUN="false"
```

**Important**: Before switching to production, ensure:
1. SSH key management is configured (currently uses placeholder)
2. The actual WireGuard server configuration is implemented on the VM
3. You've tested the complete flow end-to-end
4. You understand the cost implications of running VMs

## Development

### Local Development (Functions)

1. **Install Azure Functions Core Tools**
   ```bash
   npm install -g azure-functions-core-tools@4
   ```

2. **Create local.settings.json** from template
   ```bash
   cp backend/local.settings.json.template backend/local.settings.json
   # Edit local.settings.json with your values
   ```

3. **Install Python dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Run locally**
   ```bash
   cd backend
   func start
   ```

### Local Development (SPA)

Since the SPA uses CDN resources and no build step:
1. Open `index.html` in a browser
2. Use a local web server for proper CORS:
   ```bash
   python -m http.server 8000
   ```
3. Navigate to `http://localhost:8000`

**Note**: Authentication won't work locally (requires Azure SWA runtime).

## Security Considerations

### Current Implementation (MVP)
- ✅ Authentication via Azure SWA built-in auth
- ✅ Email-based allowlist
- ✅ 30-minute auto-teardown
- ⚠️ Placeholder SSH key management
- ⚠️ Basic error handling
- ⚠️ Minimal logging

### Production Hardening Needed
1. **SSH Key Management**
   - Store private keys in Azure Key Vault
   - Implement key rotation
   - Generate ephemeral keys per VM

2. **Network Security**
   - Add Network Security Group rules
   - Limit WireGuard port access
   - Consider VNet integration

3. **Secrets Management**
   - Move all secrets to Key Vault
   - Use Managed Identity exclusively
   - Rotate credentials regularly

4. **Monitoring & Alerts**
   - Set up Application Insights
   - Alert on failed provisioning
   - Track usage metrics
   - Monitor costs

5. **Rate Limiting**
   - Limit VMs per user
   - Implement request throttling
   - Add cooldown periods

6. **Error Handling**
   - Implement retry logic with exponential backoff
   - Add circuit breakers
   - Graceful degradation
   - Better user feedback

7. **Compliance**
   - Audit logging for all operations
   - Data retention policies
   - Privacy considerations
   - Terms of service

## Troubleshooting

### Function App Issues

**Problem**: Functions not deploying
```bash
# Check deployment logs
az functionapp deployment list-publishing-credentials \
  --name wireguard-functions \
  --resource-group wireguard-rg
```

**Problem**: Authentication failing
- Verify X-MS-CLIENT-PRINCIPAL header is being set (check SWA linkage)
- Confirm email is in ALLOWED_EMAILS setting
- Check Function App logs in Azure Portal

### Static Web App Issues

**Problem**: Can't access the app
- Verify authentication providers are configured
- Check routes.json is deployed
- Confirm API linkage to Function App

**Problem**: API calls failing
- Verify Functions are linked as backend
- Check CORS settings
- Review browser console for errors

### VM Provisioning Issues

**Problem**: VM creation failing (when DRY_RUN=false)
- Verify subscription has quota for Standard_B1ls
- Check Managed Identity has Contributor role
- Confirm resource group exists
- Review Function App logs

## File Structure

```
.
├── index.html                          # SPA entry point
├── routes.json                         # SWA routing configuration
├── .github/
│   └── workflows/
│       ├── swa-deploy.yml             # SWA deployment workflow
│       └── functions-deploy.yml        # Functions deployment workflow
├── backend/
│   ├── host.json                       # Function App configuration
│   ├── requirements.txt                # Python dependencies
│   ├── local.settings.json.template    # Template for local dev
│   ├── .funcignore                     # Files to exclude from deployment
│   ├── .gitignore                      # Git ignore rules
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── auth.py                     # Authentication utilities
│   │   └── wireguard.py                # WireGuard config generation
│   └── functions/
│       ├── http_start/                 # HTTP trigger to start orchestration
│       │   ├── function.json
│       │   └── __init__.py
│       ├── orchestrator/               # Main orchestration logic
│       │   ├── function.json
│       │   └── __init__.py
│       ├── create_vm_and_wireguard/    # Activity: provision VM
│       │   ├── function.json
│       │   └── __init__.py
│       ├── teardown_vm/                # Activity: delete VM
│       │   ├── function.json
│       │   └── __init__.py
│       └── status_proxy/               # HTTP: check orchestration status
│           ├── function.json
│           └── __init__.py
└── README.md                           # This file
```

## TODO / Future Enhancements

### Short Term
- [ ] Implement actual WireGuard server configuration via cloud-init
- [ ] Add SSH key management with Key Vault
- [ ] Implement proper error handling and retry logic
- [ ] Add more detailed status updates in orchestration

### Medium Term
- [ ] Support multiple concurrent VMs per user
- [ ] Add custom VM lifetime configuration
- [ ] Implement VM suspend/resume instead of delete
- [ ] Add QR code generation for mobile config
- [ ] Support for multiple regions

### Long Term
- [ ] Support for other VPN protocols (OpenVPN, IKEv2)
- [ ] Multi-cloud support (AWS, GCP)
- [ ] Web-based VPN client (WebRTC)
- [ ] Usage analytics and reporting
- [ ] Admin dashboard for allowlist management

## Cost Estimates

### With DRY_RUN=true
- **Cost**: ~$0/month (only Function App execution time, minimal)

### With DRY_RUN=false
- **VM (Standard_B1ls)**: ~$3.80/month if running 24/7, ~$0.08/hour
- **Storage**: ~$0.05/month per disk
- **Data egress**: Variable based on VPN usage
- **Function App**: First 1M executions free, then $0.20 per million
- **Static Web App**: Free tier sufficient

**Example**: 10 VPN sessions/day at 30 min each = ~$1.20/month + data egress

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
- Open a GitHub issue
- Check existing issues for solutions
- Review Azure Functions documentation

## Credits

Built with:
- [Azure Static Web Apps](https://azure.microsoft.com/services/app-service/static/)
- [Azure Durable Functions](https://docs.microsoft.com/azure/azure-functions/durable/)
- [Foundation CSS](https://get.foundation/)
- [Alpine.js](https://alpinejs.dev/)
- [WireGuard](https://www.wireguard.com/)