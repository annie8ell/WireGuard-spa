# WireGuard On-Demand Launcher

A minimal end-to-end solution for provisioning on-demand WireGuard VPN servers on Azure. This project uses a zero-build SPA frontend with Azure Static Web Apps authentication and Python-based built-in Functions that asynchronously create Ubuntu VMs with WireGuard, then automatically tear them down after 30 minutes.

> **📝 Note**: This project has migrated from Azure Durable Functions to Azure Static Web Apps built-in Functions. See [MIGRATION.md](MIGRATION.md) for details.

## Architecture Overview

### Frontend (SPA)
- **Technology**: Zero-build Single Page Application using Foundation CSS and Alpine.js (via CDN)
- **Authentication**: Azure Static Web Apps built-in authentication (Google/Microsoft)
- **Authorization**: Email allowlist with seed user `annie8ell@gmail.com` - only invited users can access
- **Deployment**: Azure Static Web Apps (single resource)

### Backend (SWA Built-in Functions)
- **Technology**: Python 3.11 Azure Static Web Apps Functions
- **Pattern**: Async HTTP API with 202 Accepted + status polling pattern
- **Authentication**: Validates X-MS-CLIENT-PRINCIPAL header against allowlist
- **Endpoints**:
  - `POST /api/start_job` - Returns 202 with operationId, initiates async VM creation
  - `GET /api/job_status?id={operationId}` - Returns job status/progress/result
- **VM Provisioning**: Directly creates Azure VMs using Azure SDK with Service Principal credentials
- **Auto-teardown**: VMs automatically deleted after 30 minutes

### Why VM instead of ACI?
WireGuard requires kernel-level TUN/TAP device support which Azure Container Instances (ACI) doesn't provide. A lightweight VM (Standard_B1ls) is the most straightforward solution for running WireGuard on Azure.

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
2. **Azure Static Web App** (Free tier works) - includes built-in Functions runtime
3. **Service Principal** with VM Contributor role (for creating/deleting VMs)
4. **Resource Group** where VMs will be created

### Required GitHub Secrets
- `AZURE_STATIC_WEB_APPS_API_TOKEN` - Deployment token for Azure Static Web Apps

### Required SWA App Settings
- `AZURE_SUBSCRIPTION_ID` - Your Azure subscription ID
- `AZURE_RESOURCE_GROUP` - Resource group where VMs will be created
- `AZURE_CLIENT_ID` - Service Principal application ID
- `AZURE_CLIENT_SECRET` - Service Principal secret
- `AZURE_TENANT_ID` - Azure AD tenant ID
- `ALLOWED_EMAILS` - Comma-separated list of authorized emails
- `DRY_RUN` - Set to 'true' for testing without creating real VMs

## Setup Instructions

### Quick Start

1. **Create Azure Static Web App**
   ```bash
   az staticwebapp create \
     --name wireguard-spa \
     --resource-group wireguard-rg \
     --location westeurope \
     --sku Free
   ```

2. **Get Deployment Token**
   ```bash
   az staticwebapp secrets list \
     --name wireguard-spa \
     --resource-group wireguard-rg \
     --query "properties.apiKey" -o tsv
   ```
   
   Add this token as `AZURE_STATIC_WEB_APPS_API_TOKEN` in GitHub Secrets.

3. **Create Service Principal** (for VM provisioning)
   ```bash
   az ad sp create-for-rbac \
     --name wireguard-spa-vm-provisioner \
     --role "Virtual Machine Contributor" \
     --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/wireguard-rg
   ```
   
   Note the output: `appId`, `password`, `tenant` - you'll need these for app settings.

4. **Configure App Settings**
   
   In Azure Portal or via CLI:
   ```bash
   SUBSCRIPTION_ID=$(az account show --query id -o tsv)
   
   az staticwebapp appsettings set \
     --name wireguard-spa \
     --resource-group wireguard-rg \
     --setting-names \
       AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
       AZURE_RESOURCE_GROUP="wireguard-rg" \
       AZURE_CLIENT_ID="<appId from step 3>" \
       AZURE_CLIENT_SECRET="<password from step 3>" \
       AZURE_TENANT_ID="<tenant from step 3>" \
       ALLOWED_EMAILS="user1@example.com,user2@example.com" \
       DRY_RUN="true"
   ```
   
   **Note**: Start with `DRY_RUN=true` to test without creating real VMs.

5. **Configure Authentication**
   
   In Azure Portal:
   - Navigate to your Static Web App
   - Go to **Authentication**
   - Configure identity providers (Google and/or Microsoft)

6. **Deploy**
   
   Push to `main` branch or manually trigger the workflow:
   ```bash
   # Via GitHub CLI
   gh workflow run azure-static-web-apps.yml
   
   # Or push to main branch
   git push origin main
   ```

The GitHub Actions workflow will deploy both the SPA and API functions to Azure Static Web Apps.

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

### Deployment Issues

**Problem**: Workflow fails to deploy
- Verify `AZURE_STATIC_WEB_APPS_API_TOKEN` secret is set correctly
- Check workflow logs in GitHub Actions
- Ensure Python requirements can be installed

**Problem**: Authentication failing
- Verify authentication providers are configured in Azure Portal
- Confirm email is in ALLOWED_EMAILS app setting
- Check browser developer console for errors

### API Issues

**Problem**: API calls failing
- Check app settings are configured (ALLOWED_EMAILS, etc.)
- Review browser console for CORS errors
- Check SWA logs in Azure Portal

**Problem**: Job stuck in "pending" or "running"
- Verify UPSTREAM_BASE_URL and UPSTREAM_API_KEY are set
- Check upstream provider is responding
- Review function logs in Azure Portal
- If using DRY_RUN, ensure it's set to "true"

## File Structure

```
.
├── index.html                          # SPA entry point
├── staticwebapp.config.json            # SWA configuration (routing, auth)
├── .github/
│   └── workflows/
│       └── azure-static-web-apps.yml   # SWA deployment workflow
├── api/                                # SWA built-in Functions
│   ├── requirements.txt                # Python dependencies
│   ├── start_job/                      # POST /api/start_job
│   │   ├── function.json
│   │   └── __init__.py
│   ├── job_status/                     # GET /api/job_status
│   │   ├── function.json
│   │   └── __init__.py
│   └── shared/
│       ├── __init__.py
│       ├── auth.py                     # Authentication utilities
│       ├── status_store.py             # In-memory job tracking
│       └── upstream.py                 # Upstream provider integration
├── infra/
│   └── main.bicep                      # Infrastructure as Code (SWA only)
└── README.md                           # This file
```

## API Endpoints

### POST /api/start_job
Start a new VM and WireGuard provisioning job.

**Request:**
```json
{
  "action": "provision"  // optional, for extensibility
}
```

**Response:** 202 Accepted
```json
{
  "operationId": "uuid-here",
  "status": "accepted",
  "statusQueryUrl": "/api/job_status?id=uuid-here"
}
```

**Headers:**
- `Location: /api/job_status?id=uuid-here`

### GET /api/job_status?id={operationId}
Check the status of a provisioning job.

**Response:** 200 OK (in progress)
```json
{
  "operationId": "uuid-here",
  "status": "running",
  "progress": "Installing WireGuard...",
  "createdAt": "2024-10-20T10:00:00Z",
  "lastUpdatedAt": "2024-10-20T10:02:30Z"
}
```

**Response:** 200 OK (completed)
```json
{
  "operationId": "uuid-here",
  "status": "completed",
  "progress": "Completed successfully",
  "createdAt": "2024-10-20T10:00:00Z",
  "lastUpdatedAt": "2024-10-20T10:05:00Z",
  "result": {
    "vmName": "wg-vm-12345",
    "publicIp": "203.0.113.42",
    "confText": "[Interface]\nPrivateKey=...\n..."
  }
}
```

**Response:** 200 OK (failed)
```json
{
  "operationId": "uuid-here",
  "status": "failed",
  "progress": "Failed",
  "error": "VM creation failed: quota exceeded",
  "createdAt": "2024-10-20T10:00:00Z",
  "lastUpdatedAt": "2024-10-20T10:03:00Z"
}
```

## TODO / Future Enhancements

### Short Term
- [ ] Upgrade status store from in-memory to Redis or Azure Table Storage
- [ ] Add webhook support for upstream provider notifications
- [ ] Implement proper error handling and retry logic
- [ ] Add QR code generation for mobile WireGuard config

### Medium Term
- [ ] Support multiple concurrent VMs per user
- [ ] Add custom VM lifetime configuration
- [ ] Add usage analytics and reporting
- [ ] Admin dashboard for allowlist management

### Long Term
- [ ] Support for other VPN protocols (OpenVPN, IKEv2)
- [ ] Multi-cloud support (AWS, GCP)
- [ ] Web-based VPN client (WebRTC)

## Cost Estimates

### Azure Static Web App
- **Free tier**: Sufficient for this application
- **SWA Functions**: First 1M requests/month free
- **Bandwidth**: First 100 GB/month free

### With DRY_RUN=true
- **Cost**: ~$0/month (no external resources)

### With real upstream provider
- Costs depend on your upstream provider's pricing
- Typical VM costs: ~$0.01-0.08/hour depending on size and region
- Data egress: Variable based on VPN usage

**Example**: Using Azure VMs via upstream, 10 sessions/day at 30 min each = ~$1-2/month + data egress

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