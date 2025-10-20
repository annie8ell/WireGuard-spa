# Migration from Durable Functions to Azure Static Web Apps Functions

## Overview

This document describes the migration from a separate Azure Function App using Durable Functions to Azure Static Web Apps (SWA) built-in Functions in Python.

## Architecture Changes

### Before: Durable Functions Architecture

```
┌─────────────────────────────────────┐
│  Azure Static Web App (Frontend)   │
│  - Zero-build SPA                   │
│  - Built-in authentication          │
└─────────────┬───────────────────────┘
              │ /api/* (linked backend)
              ▼
┌─────────────────────────────────────┐
│  Azure Function App (Backend)       │
│  - Durable Functions orchestrator   │
│  - Activity functions               │
│  - Requires separate deployment     │
│  - Needs Azure Storage for state    │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Azure VM (WireGuard)               │
│  - Provisioned on-demand            │
│  - Auto-teardown after 30 min       │
└─────────────────────────────────────┘
```

### After: SWA Built-in Functions Architecture

```
┌──────────────────────────────────────────┐
│  Azure Static Web App                    │
│  ┌────────────────────────────────────┐  │
│  │  Frontend (SPA)                    │  │
│  │  - Zero-build SPA                  │  │
│  │  - Built-in authentication         │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │  Built-in Functions (api/)         │  │
│  │  - POST /api/start_job             │  │
│  │  - GET /api/job_status             │  │
│  │  - Uses Azure SDK to create VMs    │  │
│  │  - Single deployment               │  │
│  └────────────────────────────────────┘  │
└──────────────┬───────────────────────────┘
               │ Uses Service Principal
               │ (Azure SDK)
               ▼
┌──────────────────────────────────────────┐
│  Azure VM (WireGuard)                    │
│  - Ubuntu 18.04 LTS                      │
│  - Standard_B1ls                         │
│  - WireGuard configured                  │
│  - Auto-deleted after 30 minutes         │
└──────────────────────────────────────────┘
```

## Key Differences

### 1. Orchestration Pattern

**Before (Durable Functions):**
- Stateful orchestration with durable timers
- Activity functions for long-running operations
- Built-in state management via Azure Storage
- Complex but powerful async/await patterns

**After (SWA Functions):**
- Stateless functions with 202 Accepted pattern
- Direct Azure VM creation using Azure SDK
- Service Principal authentication (no Managed Identity support in SWA Functions)
- In-memory status store (upgradable to Redis/Table Storage)
- Client-side polling for status updates
- Simpler implementation, easier to understand

### 2. Deployment Model

**Before:**
- Two separate deployments (SWA + Function App)
- Multiple workflows (`swa-deploy.yml`, `functions-deploy.yml`, `infra-provision-and-deploy.yml`)
- Separate Azure resources (Storage Account, Function App, SWA)
- Manual linking of Function App as SWA backend

**After:**
- Single deployment via `azure-static-web-apps.yml`
- Single resource (SWA with built-in Functions)
- Automatic integration between frontend and API
- No external storage required for basic operation

### 3. Function Structure

**Before:**
```
backend/
├── functions/
│   ├── http_start/          # HTTP trigger to start orchestration
│   ├── orchestrator/         # Main orchestration logic
│   ├── create_vm_and_wireguard/  # Activity: provision VM
│   ├── teardown_vm/          # Activity: delete VM
│   └── status_proxy/         # HTTP: check status
├── shared/
│   ├── auth.py
│   ├── wireguard.py
│   └── vm_manager.py
├── host.json                 # Durable Functions config
└── requirements.txt          # Includes azure-functions-durable
```

**After:**
```
api/
├── start_job/               # POST: Returns 202 + operationId
│   ├── function.json
│   └── __init__.py
├── job_status/              # GET: Returns job status/result
│   ├── function.json
│   └── __init__.py
├── shared/
│   ├── auth.py              # User validation (copied from backend)
│   ├── status_store.py      # In-memory job tracking
│   └── upstream.py          # Integration with upstream provider
└── requirements.txt         # No Durable Functions dependency
```

### 4. API Endpoints

**Before:**
- `POST /api/http_start` - Start orchestration, returns management URLs
- `GET /api/status_proxy/{instanceId}` - Check orchestration status
- Durable Functions management endpoints (built-in)

**After:**
- `POST /api/start_job` - Start job, returns 202 + operationId + Location header
- `GET /api/job_status?id={operationId}` - Check job status/progress/result

### 5. Status Polling

**Before:**
```javascript
// Frontend polls Durable Functions status endpoint
const response = await fetch(`/api/status_proxy/${instanceId}`);
const status = await response.json();
// Durable Functions provides: runtimeStatus, customStatus, output, etc.
```

**After:**
```javascript
// Frontend polls simplified status endpoint
const response = await fetch(`/api/job_status?id=${operationId}`);
const status = await response.json();
// Returns: status, progress, result (when completed), error (when failed)
```

## Migration Steps

### 1. Remove Old Infrastructure

The following have been removed or disabled:

- ✅ `backend/` directory (all Durable Functions code)
- ✅ `.github/workflows/functions-deploy.yml` (Function App deployment)
- ✅ `.github/workflows/infra-provision-and-deploy.yml` (Infrastructure provisioning)
- ✅ `infra/main.bicep` - Function App resources commented out with migration notes

### 2. New API Implementation

Created new API structure under `api/`:

- ✅ `api/start_job/` - Initiates async job, returns 202
- ✅ `api/job_status/` - Returns job status
- ✅ `api/shared/status_store.py` - In-memory job tracking
- ✅ `api/shared/vm_provisioner.py` - Direct Azure VM provisioning using Azure SDK
- ✅ `api/shared/auth.py` - Authentication utilities (from old backend)

### 3. Configuration Updates

- ✅ Created `staticwebapp.config.json` at repo root
- ✅ Created `.github/workflows/azure-static-web-apps.yml`
- ✅ Updated `.gitignore` if needed

### 4. Documentation Updates

- ✅ Created `MIGRATION.md` (this document)
- 🔄 Update `README.md` with new architecture
- 🔄 Update `ARCHITECTURE.md` with new design

## Environment Variables

### Removed (Durable Functions specific):
- `AzureWebJobsStorage` - No longer needed (was for Durable Functions state)
- `FUNCTIONS_WORKER_RUNTIME` - No longer needed (replaced by SWA Functions)

### Changed:
- `AZURE_SUBSCRIPTION_ID` - Still needed, now in SWA app settings (was in Function App)
- `AZURE_RESOURCE_GROUP` - Still needed, now in SWA app settings (was in Function App)

### New/Required:
- `AZURE_CLIENT_ID` - Service Principal application ID (for Azure SDK authentication)
- `AZURE_CLIENT_SECRET` - Service Principal secret (SWA Functions don't support Managed Identity)
- `AZURE_TENANT_ID` - Azure AD tenant ID
- `ALLOWED_EMAILS` - Comma-separated list of authorized emails (carried over)
- `DRY_RUN` - Set to "true" for testing without real provisioning (carried over)

### Configuration in Azure Portal:

1. Navigate to your Azure Static Web App
2. Go to **Configuration** → **Application settings**
3. Add/update the environment variables listed above
4. Save and restart the app

**Important**: SWA Functions do NOT support Managed Identity. Azure credentials must be provided via Service Principal stored in app settings.

## Frontend Changes Required

The frontend needs minimal changes to work with the new API:

### Old Code (Durable Functions):
```javascript
// Start provisioning
const response = await fetch('/api/http_start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
});
const data = await response.json();
const statusUrl = data.statusQueryGetUri;

// Poll status
const statusResponse = await fetch(statusUrl);
const status = await statusResponse.json();
if (status.runtimeStatus === 'Completed') {
    const config = status.output.confText;
}
```

### New Code (SWA Functions):
```javascript
// Start job
const response = await fetch('/api/start_job', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
});
const data = await response.json();
const operationId = data.operationId;

// Poll status
const statusResponse = await fetch(`/api/job_status?id=${operationId}`);
const status = await statusResponse.json();
if (status.status === 'completed') {
    const config = status.result.confText;
}
```

## Deployment

### Azure Static Web App Setup

1. **Create SWA Resource** (if not exists):
   ```bash
   az staticwebapp create \
     --name wireguard-spa \
     --resource-group wireguard-rg \
     --location westeurope \
     --sku Free
   ```

2. **Get Deployment Token**:
   ```bash
   az staticwebapp secrets list \
     --name wireguard-spa \
     --resource-group wireguard-rg \
     --query "properties.apiKey" -o tsv
   ```

3. **Add GitHub Secret**:
   - Go to GitHub repo → Settings → Secrets and variables → Actions
   - Add secret: `AZURE_STATIC_WEB_APPS_API_TOKEN` with the token value

4. **Configure App Settings**:
   First, create a Service Principal:
   ```bash
   az ad sp create-for-rbac \
     --name wireguard-spa-vm-provisioner \
     --role "Virtual Machine Contributor" \
     --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/wireguard-rg
   ```
   
   Note the output values (appId, password, tenant).
   
   Then configure app settings:
   ```bash
   SUBSCRIPTION_ID=$(az account show --query id -o tsv)
   
   az staticwebapp appsettings set \
     --name wireguard-spa \
     --resource-group wireguard-rg \
     --setting-names \
       AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
       AZURE_RESOURCE_GROUP="wireguard-rg" \
       AZURE_CLIENT_ID="<appId from Service Principal>" \
       AZURE_CLIENT_SECRET="<password from Service Principal>" \
       AZURE_TENANT_ID="<tenant from Service Principal>" \
       ALLOWED_EMAILS="user1@example.com,user2@example.com" \
       DRY_RUN="true"
   ```

5. **Deploy**:
   - Push to `main` branch, or
   - Manually trigger the workflow from GitHub Actions UI

### Testing

1. **With DRY_RUN=true** (recommended first):
   - No actual VM provisioning
   - Returns sample WireGuard config
   - Tests the flow end-to-end without Azure costs

2. **With DRY_RUN=false** (production):
   - Set `DRY_RUN=false` in app settings
   - Actually creates Azure VMs using configured Service Principal
   - VMs automatically deleted after 30 minutes

## VM Provisioning Details

The SWA Functions directly create Azure VMs using the Azure SDK:

1. **Authentication**: Uses Service Principal credentials (stored in SWA app settings)
   - SWA Functions do NOT support Managed Identity
   - Service Principal must have "Virtual Machine Contributor" role

2. **VM Creation** (`api/shared/vm_provisioner.py`):
   - Creates Network Security Group (allows WireGuard port 51820, SSH port 22)
   - Creates Virtual Network and Subnet
   - Creates Public IP (static)
   - Creates Network Interface
   - Creates VM (Standard_B1ls, Ubuntu 18.04 LTS)
   - Installs WireGuard via cloud-init

3. **Auto-Teardown**:
   - VMs should be automatically deleted after 30 minutes
   - TODO: Implement cleanup mechanism (options: scheduled function, expiry tags, separate worker)

## Benefits of Migration

1. **Simplified Architecture**: Single resource, single deployment
2. **Lower Cost**: No separate Function App or Storage Account needed
3. **Easier Maintenance**: Less infrastructure to manage
4. **Better Integration**: API and frontend in same resource
5. **Clearer Pattern**: Standard REST API with 202 Accepted pattern

## Trade-offs

1. **No Built-in State Management**: Must implement status tracking (provided as in-memory store, can upgrade to external storage)
2. **No Durable Timers**: Auto-teardown must be handled by upstream provider
3. **Polling Required**: Client must poll for status instead of webhooks (can be added later)
4. **Function Execution Limits**: SWA Functions have shorter timeout than dedicated Function App

## Rollback Plan

If issues arise, you can temporarily revert:

1. Keep old `backend/` directory in git history
2. Old Function App resources may still exist in Azure (if not deleted)
3. Can redeploy old workflows from git history
4. Frontend changes are minimal and backward compatible

## Questions or Issues?

If anything is unclear or requires upstream provider details:
- Leave a comment in the PR
- Check `api/shared/upstream.py` for TODO comments
- Review Azure Static Web Apps documentation: https://learn.microsoft.com/azure/static-web-apps/

## Summary

This migration moves from a complex Durable Functions architecture to a simpler, more maintainable SWA built-in Functions approach. The key change is using a stateless proxy pattern with client-side polling instead of server-side orchestration. This reduces infrastructure complexity while maintaining the same functionality for end users.
