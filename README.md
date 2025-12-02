# WireGuard Ephemeral VPN

A simplified solution for provisioning ephemeral WireGuard VPN servers on Azure. Deploy with one click, connect via QR code, and the VM automatically self-destructs after 30 minutes.

## Features

- ✅ **One-click deployment** - Deploy all infrastructure via GitHub Actions
- ✅ **QR code access** - Scan to configure WireGuard on mobile
- ✅ **Auto-shutdown** - VMs automatically terminate after 30 minutes
- ✅ **Access control** - Restricted to authorized users only
- ✅ **West Europe** - VMs deployed in Azure West Europe region
- ✅ **Destroy workflow** - Clean up all resources with one command

## Quick Start

### Prerequisites

1. **Azure Subscription** with permissions to create resources
2. **GitHub repository** forked from this project
3. **Service Principal** with Contributor role

### Step 1: Create Service Principal

```bash
# Login to Azure
az login

# Create Service Principal with Contributor role
az ad sp create-for-rbac \
  --name "wireguard-vpn-sp" \
  --role "Contributor" \
  --scopes "/subscriptions/YOUR_SUBSCRIPTION_ID"
```

Note the output:
- `appId` → AZURE_CLIENT_ID
- `password` → AZURE_SECRET
- `tenant` → AZURE_TENANT_ID

### Step 2: Configure GitHub Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Description |
|------------|-------------|
| `AZURE_CLIENT_ID` | Service Principal application ID |
| `AZURE_SECRET` | Service Principal password |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

### Step 3: Deploy Infrastructure

1. Go to **Actions** tab in your repository
2. Select **"Deploy Ephemeral WireGuard VPN Infrastructure"**
3. Click **"Run workflow"**
4. Choose options:
   - Location: `westeurope` (default)
   - Resource group: `wireguard-vpn-rg` (default)
   - Dry run: `false` for real deployment
5. Click **"Run workflow"**

### Step 4: Configure User Access

After deployment, invite the authorized user:

1. Go to **Azure Portal → Static Web Apps → wireguard-vpn-swa**
2. Go to **Role management**
3. Click **Invite**
4. Enter: `awwsawws@gmail.com`
5. Select role: `invited`
6. Click **Generate invitation link**

### Step 5: Access the VPN

1. Navigate to the Static Web App URL (shown in deployment output)
2. Sign in with Google
3. Click **"Request VPN"**
4. Scan the QR code with WireGuard mobile app
5. Connect and enjoy your VPN!

The VM will automatically terminate after 30 minutes.

## Workflows

### Deploy Workflow

Provisions all infrastructure:
- Azure Resource Group
- Azure Static Web App
- Configures app settings for VM provisioning

```bash
# Run via GitHub Actions UI or CLI
gh workflow run deploy.yml
```

### Destroy Workflow

Removes all infrastructure:
- Deletes all VMs
- Deletes network resources
- Deletes the resource group

```bash
# Run via GitHub Actions UI
# Must type "DESTROY" to confirm
gh workflow run destroy.yml
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      GitHub Actions                              │
│  ┌─────────────────┐              ┌─────────────────────────┐  │
│  │  Deploy         │              │  Destroy                 │  │
│  │  Workflow       │              │  Workflow                │  │
│  └────────┬────────┘              └────────────┬────────────┘  │
└───────────┼────────────────────────────────────┼────────────────┘
            │                                     │
            ▼                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Azure                                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Resource Group (wireguard-vpn-rg)             │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │           Static Web App (wireguard-vpn-swa)         │ │ │
│  │  │                                                      │ │ │
│  │  │  ┌──────────────┐    ┌─────────────────────────┐   │ │ │
│  │  │  │    SPA       │    │   Python Functions API   │   │ │ │
│  │  │  │  (QR Code)   │    │   (VM Provisioning)      │   │ │ │
│  │  │  └──────────────┘    └─────────────────────────┘   │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │      WireGuard VM (Ubuntu 22.04, Standard_B1ls)      │ │ │
│  │  │                                                      │ │ │
│  │  │  • Auto-created on demand                           │ │ │
│  │  │  • Auto-shutdown after 30 minutes                   │ │ │
│  │  │  • WireGuard server with generated keys             │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Access Control

This application is restricted to **awwsawws@gmail.com** only.

- Authentication: Google Sign-In via Azure SWA
- Authorization: Role-based access with 'invited' role
- The user must be explicitly invited in Azure Portal

## Auto-Shutdown

VMs are configured with 30-minute auto-shutdown:
- Azure DevTest Labs auto-shutdown schedule
- Triggers 30 minutes after VM creation
- No manual cleanup required

## Cost Estimate

- **Static Web App**: Free tier ($0/month)
- **VM**: Standard_B1ls (~$0.01/hour)
- **Typical usage**: ~$0.005 per VPN session (30 min)

## Testing

### Dry Run Mode

Test the workflow without creating real resources:

1. Run deploy workflow with `dry_run: true`
2. The UI will work but no actual VM is created
3. Useful for testing authentication and UI flow

### Verify Access Control

1. Try accessing with an unauthorized account → Should show "Access Denied"
2. Try accessing with awwsawws@gmail.com → Should allow access

### Verify Auto-Shutdown

1. Request a VPN
2. Note the VM creation time
3. After 30 minutes, verify VM is terminated in Azure Portal

## File Structure

```
.
├── .github/
│   └── workflows/
│       ├── deploy.yml              # Deploy infrastructure
│       └── destroy.yml             # Destroy infrastructure
├── api/                            # Python Functions API
│   ├── start_job/                  # POST /api/start_job
│   ├── job_status/                 # GET /api/job_status
│   └── shared/
│       ├── vm_provisioner.py       # VM creation logic
│       └── wireguard_docker_setup.sh
├── frontend/
│   └── public/
│       ├── index.html              # Main SPA with QR code
│       ├── login.html              # Login page
│       ├── unauthorized.html       # Access denied page
│       └── staticwebapp.config.json
├── infra/
│   └── main.bicep                  # Infrastructure as Code
└── README.md                       # This file
```

## Troubleshooting

### Deployment Fails

1. Check GitHub secrets are configured correctly
2. Verify Service Principal has Contributor role
3. Check workflow logs for specific errors

### Access Denied After Login

1. Ensure user is invited to 'invited' role in Azure Portal
2. Check SWA authentication configuration
3. Try clearing browser cookies and signing in again

### VM Not Creating

1. Check Azure subscription quotas
2. Verify Service Principal credentials in SWA app settings
3. Check function logs in Azure Portal

### QR Code Not Showing

1. Wait for VM provisioning to complete
2. Check browser console for JavaScript errors
3. Try refreshing the page

## Security

- All secrets stored in GitHub Secrets
- Service Principal with minimal required permissions
- Authentication required for all routes
- VMs auto-terminate to minimize exposure
- No persistent storage of VPN keys

## License

MIT License - See LICENSE file for details
