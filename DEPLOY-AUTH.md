# Azure Static Web Apps Invitations and Role-Based Authorization Setup

This document provides comprehensive instructions for deploying the WireGuard SPA with Azure Static Web Apps (SWA) invitations and role-based authorization. The integrated Functions API is protected so only users with the `invited` role can access it.

**Important**: This deployment uses the Azure Static Web Apps Invitations feature to manage user access via the `invited` role.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Step 1: Deploy Azure Resources](#step-1-deploy-azure-resources)
5. [Step 2: Configure Function App Managed Identity](#step-2-configure-function-app-managed-identity)
6. [Step 3: Deploy the Application](#step-3-deploy-the-application)
7. [Step 4: Link Function App as SWA Integrated API](#step-4-link-function-app-as-swa-integrated-api)
8. [Step 5: Enable and Configure SWA Invitations](#step-5-enable-and-configure-swa-invitations)
9. [Step 6: Invite Users and Assign Roles](#step-6-invite-users-and-assign-roles)
10. [Step 7: Verify Configuration](#step-7-verify-configuration)
11. [Step 8: End-to-End Testing](#step-8-end-to-end-testing)
12. [Troubleshooting](#troubleshooting)

## Overview

This deployment uses **Azure Static Web Apps Invitations** as the single authentication and authorization gate. Key points:

- **Frontend**: Zero-build SPA (index.html) trusts `/.auth/me` for auth state. UI is role-aware for display purposes only; security is NOT enforced in the browser.
- **SWA Edge**: Route-level authorization enforced via `staticwebapp.config.json` - only users with the `invited` role can access `/api/*` endpoints.
- **Backend (Functions)**: Validates the injected `X-MS-CLIENT-PRINCIPAL` header and authorizes based on the presence of the `invited` role in `clientPrincipal.userRoles`.
- **Integrated API**: The Functions app is deployed as the SWA integrated API (Option A), allowing SWA to inject the authenticated user's principal into backend requests.

## Architecture

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │
         │ HTTPS
         ▼
┌─────────────────────────────────────┐
│  Azure Static Web App (SWA)         │
│  - Built-in Auth (AAD/Google/etc)   │
│  - Invitations UI for role mgmt     │
│  - Route protection (/api/*)        │
│  - Role enforcement: "invited"      │
└────────┬────────────────────────────┘
         │
         │ Inject X-MS-CLIENT-PRINCIPAL
         ▼
┌─────────────────────────────────────┐
│  Azure Functions (Integrated API)   │
│  - Validates X-MS-CLIENT-PRINCIPAL  │
│  - Checks for "invited" role        │
│  - Durable Functions orchestration  │
│  - Managed Identity for Azure RBAC  │
└────────┬────────────────────────────┘
         │
         │ Azure SDK with Managed Identity
         ▼
┌─────────────────────────────────────┐
│  Azure Resources                    │
│  - Create/Delete VMs                │
│  - Storage (Durable state)          │
└─────────────────────────────────────┘
```

## Prerequisites

- **Azure Subscription** with permissions to create resources
- **Azure CLI** installed and configured (`az login`)
- **GitHub repository** with the WireGuard SPA code
- **GitHub Actions** access (for CI/CD workflows)
- **Git** and **GitHub CLI** (optional, for easier workflow management)

## Step 1: Deploy Azure Resources

### 1.1 Create Resource Group

```bash
LOCATION="westeurope"
RESOURCE_GROUP="wireguard-rg"

az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### 1.2 Create Storage Account (for Durable Functions)

```bash
STORAGE_ACCOUNT="wireguardstorage$(date +%s)"

az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2
```

**Important**: Save the storage account name. You'll need the connection string for the Function App.

```bash
STORAGE_CONNECTION_STRING=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query connectionString -o tsv)
```

### 1.3 Create Azure Function App

```bash
FUNCTION_APP_NAME="wireguard-functions-$(date +%s)"

az functionapp create \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --os-type Linux \
  --disable-app-insights false
```

### 1.4 Create Azure Static Web App

```bash
SWA_NAME="wireguard-spa"

az staticwebapp create \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Free
```

**Note**: For production deployments, consider using the Standard tier for enhanced features.

## Step 2: Configure Function App Managed Identity

The Function App needs permissions to create and delete VMs. We use a **system-assigned managed identity** (recommended).

### 2.1 Enable System-Assigned Managed Identity

```bash
az functionapp identity assign \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### 2.2 Grant Contributor Role to the Managed Identity

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

PRINCIPAL_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP
```

**Verify**:
```bash
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --query "[].{Role:roleDefinitionName, Scope:scope}" -o table
```

You should see the Contributor role assigned.

### 2.3 Configure Function App Settings

```bash
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AzureWebJobsStorage="$STORAGE_CONNECTION_STRING" \
    AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
    AZURE_RESOURCE_GROUP="$RESOURCE_GROUP" \
    ADMIN_USERNAME="azureuser" \
    DRY_RUN="true"
```

**Important Settings**:
- `AzureWebJobsStorage`: Required for Durable Functions state management
- `AZURE_SUBSCRIPTION_ID`: Target subscription for VM provisioning
- `AZURE_RESOURCE_GROUP`: Target resource group for VM provisioning
- `DRY_RUN`: Start with `true` to test without creating real VMs

**Note**: With managed identity, you do NOT need to set `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, or `AZURE_TENANT_ID`.

## Step 3: Deploy the Application

### 3.1 Set Up GitHub Secrets

You need the following secrets in your GitHub repository:

1. **AZURE_CREDENTIALS** (for infrastructure provisioning):
   ```bash
   az ad sp create-for-rbac \
     --name wireguard-spa-deployer \
     --role Contributor \
     --scopes /subscriptions/$SUBSCRIPTION_ID \
     --sdk-auth
   ```
   Copy the entire JSON output and save as the `AZURE_CREDENTIALS` secret.

2. **AZURE_FUNCTIONAPP_PUBLISH_PROFILE**:
   ```bash
   az functionapp deployment list-publishing-profiles \
     --name $FUNCTION_APP_NAME \
     --resource-group $RESOURCE_GROUP \
     --xml
   ```
   Copy the XML output and save as the `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` secret.

3. **AZURE_STATIC_WEB_APPS_API_TOKEN**:
   - In Azure Portal, navigate to your Static Web App
   - Go to **Manage deployment token**
   - Copy the token and save as the `AZURE_STATIC_WEB_APPS_API_TOKEN` secret

4. **AZURE_FUNCTIONAPP_NAME**:
   - Set this to your Function App name (e.g., `wireguard-functions-1234567890`)

### 3.2 Deploy Using GitHub Actions

**Option A: Automated Infrastructure Workflow**
```bash
gh workflow run "Provision Infrastructure and Deploy" \
  --field location=$LOCATION \
  --field resourceGroup=$RESOURCE_GROUP
```

**Option B: Deploy Individually**
1. Deploy Functions:
   ```bash
   gh workflow run "Deploy Azure Functions"
   ```

2. Deploy Static Web App:
   ```bash
   gh workflow run "Deploy Static Web App"
   ```

### 3.3 Verify Deployment

**Check Function App**:
```bash
az functionapp list \
  --resource-group $RESOURCE_GROUP \
  --query "[].{Name:name, State:state, DefaultHostName:defaultHostName}" -o table
```

**Check Static Web App**:
```bash
az staticwebapp list \
  --resource-group $RESOURCE_GROUP \
  --query "[].{Name:name, DefaultHostname:defaultHostname}" -o table
```

## Step 4: Link Function App as SWA Integrated API

Linking the Function App as the SWA integrated API ensures that SWA injects the `X-MS-CLIENT-PRINCIPAL` header into backend requests.

### 4.1 Link via Azure Portal

1. Navigate to your Static Web App in Azure Portal
2. In the left menu, select **APIs** (or **Backends** in newer portal versions)
3. Click **Link** and choose **Link an existing Function App**
4. Select your Function App (`$FUNCTION_APP_NAME`)
5. Set the **API location** to `/api`
6. Click **Link**

### 4.2 Link via Azure CLI

```bash
FUNCTION_APP_ID=$(az functionapp show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az staticwebapp backends link \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --backend-resource-id $FUNCTION_APP_ID \
  --backend-region $LOCATION
```

### 4.3 Verify Linking

```bash
az staticwebapp backends show \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[].{Name:name, ResourceId:backendResourceId}" -o table
```

You should see your Function App listed as a linked backend.

## Step 5: Enable and Configure SWA Invitations

### 5.1 Enable Invitations Feature

1. Navigate to your Static Web App in Azure Portal
2. Go to **Role management** (or **Invitations**)
3. If the feature is not yet visible, it may be in preview or require enabling in your subscription
4. Follow the portal instructions to enable invitations

**Note**: As of this writing, SWA Invitations may be in preview. Check the [Azure Static Web Apps documentation](https://learn.microsoft.com/en-us/azure/static-web-apps/authentication-authorization) for the latest status.

### 5.2 Configure Authentication Providers

1. In your Static Web App, navigate to **Authentication**
2. Enable the desired identity provider(s):
   - **Azure Active Directory (AAD)** - Recommended for enterprise
   - **Google** - For consumer accounts
   - **GitHub** - For developer accounts
3. Configure the provider settings (client ID, secret, etc.)

**Example: Configure Azure AD**:
```bash
# Create an Azure AD app registration
az ad app create --display-name "WireGuard SPA"

# Configure redirect URIs in the Azure Portal:
# https://<your-swa-hostname>/.auth/login/aad/callback
```

## Step 6: Invite Users and Assign Roles

### 6.1 Create the "invited" Role

The `invited` role is a custom role that you define in your Static Web App.

1. In the Azure Portal, navigate to your Static Web App
2. Go to **Role management**
3. Ensure the `invited` role is recognized (it's defined in `staticwebapp.config.json`)

### 6.2 Invite Users via Portal

1. In **Role management** or **Invitations**, click **Invite user**
2. Enter the user's email address
3. Assign the role: **invited**
4. Send the invitation

The user will receive an email with a link to accept the invitation.

### 6.3 Invite Users via Azure CLI

```bash
# Note: CLI support for invitations may vary; check documentation
# Typically done via portal for now
```

**Alternative**: Manage roles via `staticwebapp.config.json` and pre-defined user lists (less dynamic).

### 6.4 Verify User Roles

After a user accepts the invitation:
1. Have the user navigate to `https://<your-swa-hostname>/.auth/me`
2. Verify that `userRoles` includes `"invited"`

Example response:
```json
{
  "clientPrincipal": {
    "identityProvider": "aad",
    "userId": "1234567890abcdef",
    "userDetails": "user@example.com",
    "userRoles": ["authenticated", "invited"]
  }
}
```

## Step 7: Verify Configuration

### 7.1 Verify staticwebapp.config.json Deployment

Ensure `staticwebapp.config.json` is present in the deployed artifacts:

**For root index.html deployment**:
- File location: `/staticwebapp.config.json` (root of repository)

**For frontend/ build deployment**:
- File location: `/frontend/public/staticwebapp.config.json`

**Check deployed configuration**:
```bash
# Visit your SWA URL and check browser console or network tab
# SWA uses this config to enforce route rules
```

### 7.2 Test Route Protection

**Without invited role** (unauthenticated or authenticated without role):
```bash
curl -i https://<your-swa-hostname>/api/http_start
# Expected: 302 redirect to /.auth/login/aad
```

**With invited role**:
```bash
# Log in via browser, then check API access
# Expected: API responds (may be 403 if not properly authenticated, but not 302 redirect)
```

### 7.3 Check Function App Logs

Enable Application Insights or Stream Logs:
```bash
az functionapp log tail \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

Look for log entries like:
- `User <email> validated successfully with invited role`
- `User <email> does not have invited role` (for unauthorized users)

## Step 8: End-to-End Testing

### 8.1 Test with DRY_RUN=true

1. **Ensure DRY_RUN is enabled**:
   ```bash
   az functionapp config appsettings set \
     --name $FUNCTION_APP_NAME \
     --resource-group $RESOURCE_GROUP \
     --settings DRY_RUN="true"
   ```

2. **Access the SWA**:
   - Navigate to `https://<your-swa-hostname>`
   - Sign in with an invited user account
   - Verify the UI shows the user is signed in

3. **Request a VPN**:
   - Click **Request VPN** button
   - Observe the orchestration status
   - Verify you receive a sample WireGuard configuration (no actual VM is created)

4. **Check logs**:
   ```bash
   az functionapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP
   ```
   Look for:
   - `User <email> validated successfully with invited role`
   - `Started orchestration <id> for user <email>`
   - `DRY_RUN: Skipping actual VM creation`

### 8.2 Test Unauthorized Access

1. **Invite a user but do NOT assign the "invited" role**:
   - Invite via portal or use a user without the role
   - Have them sign in

2. **Attempt API access**:
   - They should NOT be able to access `/api/*` endpoints
   - SWA should block at the edge (before reaching Functions)
   - Browser network tab should show 302 redirect or 403 response

3. **Check backend logs**:
   - If the request somehow bypasses SWA, backend logs should show:
     `User <email> does not have invited role`

### 8.3 Test with DRY_RUN=false (Production Mode)

**⚠️ Warning**: This will create actual Azure VMs and incur costs.

1. **Disable DRY_RUN**:
   ```bash
   az functionapp config appsettings set \
     --name $FUNCTION_APP_NAME \
     --resource-group $RESOURCE_GROUP \
     --settings DRY_RUN="false"
   ```

2. **Restart Function App**:
   ```bash
   az functionapp restart \
     --name $FUNCTION_APP_NAME \
     --resource-group $RESOURCE_GROUP
   ```

3. **Request a VPN** (as an invited user):
   - Click **Request VPN**
   - Wait for provisioning (may take 3-5 minutes)
   - Download the WireGuard configuration
   - Import into WireGuard client (desktop or mobile)
   - Connect and verify VPN works

4. **Verify auto-teardown**:
   - Wait 30 minutes
   - Check that the VM is automatically deleted
   - Verify in Azure Portal or via CLI:
     ```bash
     az vm list --resource-group $RESOURCE_GROUP -o table
     ```

### 8.4 End-to-End Test Summary

| Test Case | Expected Result |
|-----------|-----------------|
| Unauthenticated user accesses `/` | Redirected to `/.auth/login/aad` |
| Authenticated user without `invited` role accesses `/` | Can view UI but cannot access API |
| Authenticated user without `invited` role accesses `/api/*` | 302 redirect to login or 403 |
| Authenticated user with `invited` role accesses `/` | Can view UI and access API |
| Authenticated user with `invited` role requests VPN (DRY_RUN=true) | Receives sample config |
| Authenticated user with `invited` role requests VPN (DRY_RUN=false) | VM provisioned, config downloaded |

## Troubleshooting

### Issue: User is authenticated but has no roles

**Symptoms**:
- User can sign in
- `/.auth/me` shows `userRoles: ["authenticated"]` only

**Solution**:
1. Verify the user has been invited via **Role management**
2. Check that the `invited` role was assigned during invitation
3. Have the user sign out and sign back in to refresh roles

### Issue: API returns 403 even with invited role

**Symptoms**:
- User has `invited` role in `/.auth/me`
- API requests return 403

**Possible Causes**:
1. **Backend validation failure**: Check Function App logs for authorization errors
2. **X-MS-CLIENT-PRINCIPAL not injected**: Verify Function App is linked as integrated API
3. **Old cached credentials**: Clear browser cache and sign in again

**Solution**:
```bash
# Check Function App logs
az functionapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP

# Verify API linkage
az staticwebapp backends show --name $SWA_NAME --resource-group $RESOURCE_GROUP

# Test X-MS-CLIENT-PRINCIPAL injection via a simple test function
```

### Issue: staticwebapp.config.json not being applied

**Symptoms**:
- Routes not protected as expected
- Anyone can access `/api/*`

**Solution**:
1. Verify `staticwebapp.config.json` is in the deployed artifact root
2. Check GitHub Actions deployment logs for warnings
3. Redeploy the Static Web App:
   ```bash
   gh workflow run "Deploy Static Web App"
   ```

### Issue: Managed Identity cannot create VMs

**Symptoms**:
- Function logs show permission errors
- `AuthorizationFailed` or `Forbidden` errors

**Solution**:
```bash
# Verify role assignment
PRINCIPAL_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

az role assignment list --assignee $PRINCIPAL_ID -o table

# Re-assign Contributor role if missing
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP
```

### Issue: Durable Functions state errors

**Symptoms**:
- Orchestration fails to start
- Errors about missing storage or state

**Solution**:
```bash
# Verify AzureWebJobsStorage is set
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[?name=='AzureWebJobsStorage'].{Name:name, Value:value}" -o table

# If missing, set it
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings AzureWebJobsStorage="$STORAGE_CONNECTION_STRING"
```

### Issue: Invitations feature not available

**Symptoms**:
- Cannot find **Role management** or **Invitations** in portal

**Solution**:
- Check if your subscription/region supports SWA Invitations (may be in preview)
- Upgrade to Standard tier if on Free tier
- Check [Azure Static Web Apps documentation](https://learn.microsoft.com/en-us/azure/static-web-apps/authentication-authorization) for availability

### Getting Help

- **Azure Portal**: Check Activity Log and Diagnostics for errors
- **Function App Logs**: Use `az functionapp log tail` or Application Insights
- **Static Web App Logs**: Check deployment logs in Azure Portal
- **GitHub Actions**: Review workflow run logs for deployment issues
- **Azure Documentation**: [Azure Static Web Apps](https://docs.microsoft.com/en-us/azure/static-web-apps/)

## Summary

You have successfully deployed the WireGuard SPA with Azure Static Web Apps invitations and role-based authorization. The key points:

✅ **Single Auth/Authorization Gate**: SWA handles all authentication and route-level authorization  
✅ **Role-Based Access**: Only users with the `invited` role can access the API  
✅ **Managed Identity**: Function App uses managed identity for Azure resource provisioning  
✅ **Integrated API**: Function App is deployed as SWA integrated API with X-MS-CLIENT-PRINCIPAL injection  
✅ **Secure by Default**: Authorization enforced at the edge and validated in the backend  

For production deployments, consider:
- Enabling Application Insights for monitoring
- Setting up alerts for failed provisioning
- Implementing rate limiting and usage quotas
- Regular review of invited users and role assignments
- Backup and disaster recovery planning

Happy VPN provisioning! 🚀
