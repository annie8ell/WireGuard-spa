# Setup Guide: GitHub Secrets and Azure Role Assignments

This guide provides step-by-step instructions for configuring the required GitHub repository secrets and Azure role assignments needed for deploying the WireGuard SPA application. This completes the setup process started in PR #3.

> **Setup Path**: This guide covers the **manual** setup approach with detailed step-by-step instructions. If you prefer automated setup (especially useful in GitHub Codespaces), see [SETUP-CREDENTIALS.md](SETUP-CREDENTIALS.md) for the automated approach.

## Prerequisites

Before proceeding, ensure you have:
- Azure CLI installed and logged in (`az login`)
- GitHub CLI installed (optional, for setting secrets via CLI)
- Appropriate Azure subscription permissions (Owner or Contributor role)
- Your Azure resources provisioned (see the infrastructure workflow)

## Table of Contents

1. [Required GitHub Secrets](#required-github-secrets)
2. [Static Web App Deployment Token](#1-static-web-app-deployment-token-azure_static_web_apps_api_token)
3. [Service Principal for VM Provisioning](#2-service-principal-for-vm-provisioning-swa-app-settings)
4. [Alternative: OIDC/Federated Credentials](#3-alternative-oidcfederated-credentials-advanced)
5. [Verification Checklist](#verification-checklist)

## Required GitHub Secrets

The deployment workflow requires the following secret to be set in your GitHub repository:

| Secret Name | Purpose | Used By |
|------------|---------|---------|
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Deployment token for Static Web App | Azure Static Web Apps deployment workflow |

> **Note**: With the current SWA built-in Functions architecture, only the SWA deployment token is needed for GitHub Actions. The Service Principal credentials for VM provisioning are configured as **SWA app settings** (not GitHub secrets) - see section 2 below.

## 1. Static Web App Deployment Token (AZURE_STATIC_WEB_APPS_API_TOKEN)

The deployment token is required for deploying to Azure Static Web Apps via GitHub Actions.

### Retrieving the Deployment Token

```bash
# Set your Static Web App name and resource group
SWA_NAME="your-static-web-app-name"
RESOURCE_GROUP="wireguard-spa-rg"

# Get the API key (deployment token)
az staticwebapp secrets list \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --query 'properties.apiKey' -o tsv
```

**Alternatively**, use the helper script:

```bash
# Make the script executable
chmod +x scripts/get-swa-deploy-token.sh

# Run the script
./scripts/get-swa-deploy-token.sh $SWA_NAME $RESOURCE_GROUP

# Pipe directly to GitHub secret (if using gh CLI)
./scripts/get-swa-deploy-token.sh $SWA_NAME $RESOURCE_GROUP | \
  gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN
```

### Setting the GitHub Secret

**Via GitHub Web UI:**
1. Copy the token output from the command above
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `AZURE_STATIC_WEB_APPS_API_TOKEN`
5. Value: Paste the token
6. Click **Add secret**

**Via GitHub CLI:**
```bash
# Retrieve and set in one command
az staticwebapp secrets list \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --query 'properties.apiKey' -o tsv | \
  gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN
```

## 2. Service Principal for VM Provisioning (SWA App Settings)

The SWA built-in Functions use a Service Principal to create and manage VMs. These credentials are configured as **Azure Static Web Apps application settings** (NOT GitHub secrets).

### Creating the Service Principal

```bash
# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_GROUP="wireguard-spa-rg"

# Create service principal with VM Contributor role on resource group
az ad sp create-for-rbac \
  --name "wireguard-spa-vm-provisioner" \
  --role "Virtual Machine Contributor" \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP

# Save the output values:
# - appId (this is AZURE_CLIENT_ID)
# - password (this is AZURE_CLIENT_SECRET)
# - tenant (this is AZURE_TENANT_ID)
```

### Configure SWA App Settings

These settings are configured in the Azure Portal or via Azure CLI:

```bash
SWA_NAME="your-static-web-app-name"
RESOURCE_GROUP="wireguard-spa-rg"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az staticwebapp appsettings set \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --setting-names \
    AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
    AZURE_RESOURCE_GROUP="$RESOURCE_GROUP" \
    AZURE_CLIENT_ID="<appId from above>" \
    AZURE_CLIENT_SECRET="<password from above>" \
    AZURE_TENANT_ID="<tenant from above>" \
    DRY_RUN="true"
```

**Via Azure Portal:**
1. Navigate to your Static Web App
2. Go to **Configuration** → **Application settings**
3. Add each setting with its corresponding value
4. Click **Save**

> **Security Note**: Start with `DRY_RUN=true` to test without creating real VMs. Set to `false` when ready for production.

## 3. Alternative: OIDC/Federated Credentials (Advanced)

For enhanced security with infrastructure provisioning workflows, you can use OpenID Connect (OIDC) with federated credentials instead of long-lived secrets.

> **Note**: The current SWA deployment workflow doesn't use Azure login - it only needs the SWA deployment token. OIDC would only be relevant if you add infrastructure provisioning workflows.

For OIDC setup instructions, see:
- [Azure AD Workload Identity Federation](https://docs.microsoft.com/azure/active-directory/workload-identities/workload-identity-federation)
- [GitHub Actions: Azure Login with OIDC](https://github.com/marketplace/actions/azure-login#login-with-openid-connect-oidc-recommended)
- [Configuring OpenID Connect in Azure](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)

## Verification Checklist

Before deploying, verify that everything is configured correctly:

### 1. Verify GitHub Secret

```bash
# Via GitHub CLI - list secrets (won't show values, just confirms it exists)
gh secret list | grep AZURE_STATIC_WEB_APPS_API_TOKEN
```

### 2. Verify Service Principal

```bash
# List service principals (find yours by name)
az ad sp list --display-name "wireguard-spa-vm-provisioner" --query '[].{Name:displayName, AppId:appId}' -o table

# Verify role assignments for the service principal
APP_ID=$(az ad sp list --display-name "wireguard-spa-vm-provisioner" --query '[0].appId' -o tsv)
az role assignment list --assignee $APP_ID --output table
```

### 3. Verify Static Web App Configuration

```bash
SWA_NAME="your-static-web-app-name"
RESOURCE_GROUP="wireguard-spa-rg"

# Check Static Web App details
az staticwebapp show \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --query '{Name:name, DefaultHostname:defaultHostname}' -o table

# Verify app settings (including Service Principal credentials)
az staticwebapp appsettings list \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table
```

### Final Checklist

- [ ] GitHub secret `AZURE_STATIC_WEB_APPS_API_TOKEN` is set
- [ ] Azure Static Web App exists
- [ ] Service Principal created with VM Contributor role
- [ ] SWA app settings configured:
  - [ ] `AZURE_SUBSCRIPTION_ID`
  - [ ] `AZURE_RESOURCE_GROUP`
  - [ ] `AZURE_CLIENT_ID`
  - [ ] `AZURE_CLIENT_SECRET`
  - [ ] `AZURE_TENANT_ID`
  - [ ] `DRY_RUN` (set to "true" for testing)
- [ ] User roles configured in SWA (assign users to 'invited' role)

## Troubleshooting

### Deployment Fails

If SWA deployment fails:
1. Verify the `AZURE_STATIC_WEB_APPS_API_TOKEN` secret is set correctly
2. Check GitHub Actions workflow logs
3. Ensure the Static Web App resource exists in Azure

### VM Provisioning Fails

If VM provisioning fails (after deployment):
1. Verify Service Principal credentials in SWA app settings
2. Check Service Principal has VM Contributor role assigned
3. Ensure `AZURE_RESOURCE_GROUP` exists and is accessible
4. Review SWA Function logs in Azure Portal
5. Test with `DRY_RUN=true` first

### Permission Denied Errors

If you get permission errors:
1. Verify the Service Principal has the correct role assigned
2. Check the scope of the role assignment (resource group)
3. Wait a few minutes for role assignments to propagate

## Next Steps

After completing this setup:

1. **Deploy the application**:
   ```bash
   # Push to main branch or manually trigger workflow
   gh workflow run azure-static-web-apps.yml
   ```

2. **Test with DRY_RUN mode**:
   - Ensure `DRY_RUN=true` is set in SWA app settings
   - Test the complete flow without creating actual VMs
   - Verify authentication and UI work correctly

3. **Configure authentication** in your Static Web App:
   - Add Google and/or Microsoft identity providers (Azure Portal)
   - Assign users to 'invited' role in Role management

4. **Enable production mode** when ready:
   - Set `DRY_RUN=false` in SWA app settings
   - Test with actual VM provisioning
   - Monitor costs and usage

For more information, see the [README.md](README.md) and [MIGRATION.md](MIGRATION.md) files.
