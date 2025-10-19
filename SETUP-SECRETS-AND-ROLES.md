# Setup Guide: GitHub Secrets and Azure Role Assignments

This guide provides step-by-step instructions for configuring the required GitHub repository secrets and Azure role assignments needed for deploying the WireGuard SPA application. This completes the setup process started in PR #3.

## Prerequisites

Before proceeding, ensure you have:
- Azure CLI installed and logged in (`az login`)
- GitHub CLI installed (optional, for setting secrets via CLI)
- Appropriate Azure subscription permissions (Owner or Contributor role)
- Your Azure resources provisioned (see the infrastructure workflow)

## Table of Contents

1. [Required GitHub Secrets](#required-github-secrets)
2. [Service Principal Setup (AZURE_CREDENTIALS)](#1-service-principal-setup-azure_credentials)
3. [Function App Publish Profile (AZURE_FUNCTIONAPP_PUBLISH_PROFILE)](#2-function-app-publish-profile-azure_functionapp_publish_profile)
4. [Static Web App Deployment Token (AZURE_STATIC_WEB_APPS_API_TOKEN)](#3-static-web-app-deployment-token-azure_static_web_apps_api_token)
5. [Function App Name (AZURE_FUNCTIONAPP_NAME)](#4-function-app-name-azure_functionapp_name)
6. [Managed Identity Role Assignments](#5-managed-identity-role-assignments)
7. [Alternative: OIDC/Federated Credentials](#6-alternative-oidc-federated-credentials)
8. [Verification Checklist](#verification-checklist)

## Required GitHub Secrets

The deployment workflows require the following secrets to be set in your GitHub repository:

| Secret Name | Purpose | Used By |
|------------|---------|---------|
| `AZURE_CREDENTIALS` | Service Principal for Azure authentication | Infrastructure provisioning, deployment workflows |
| `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` | Publish profile for Function App deployment | Backend deployment workflow |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Deployment token for Static Web App | Frontend deployment workflow |
| `AZURE_FUNCTIONAPP_NAME` | Name of the Azure Function App | Backend deployment workflow |

## 1. Service Principal Setup (AZURE_CREDENTIALS)

### Creating the Service Principal

The Service Principal is used by GitHub Actions to authenticate with Azure and provision resources.

#### Option A: Contributor Role on Subscription (Recommended for Full Control)

```bash
# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Create service principal with Contributor role on subscription
az ad sp create-for-rbac \
  --name "wireguard-spa-deployer" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID \
  --sdk-auth

# Save the entire JSON output (it will look like this):
# {
#   "clientId": "xxxx",
#   "clientSecret": "xxxx",
#   "subscriptionId": "xxxx",
#   "tenantId": "xxxx",
#   "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
#   "resourceManagerEndpointUrl": "https://management.azure.com/",
#   "activeDirectoryGraphResourceId": "https://graph.windows.net/",
#   "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
#   "galleryEndpointUrl": "https://gallery.azure.com/",
#   "managementEndpointUrl": "https://management.core.windows.net/"
# }
```

#### Option B: Contributor Role on Resource Group (More Restrictive)

If you prefer to limit permissions to a specific resource group:

```bash
# Set your resource group name
RESOURCE_GROUP="wireguard-spa-rg"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Create service principal with Contributor role on resource group
az ad sp create-for-rbac \
  --name "wireguard-spa-deployer" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

**Note:** If using resource group scope, the resource group must already exist before creating the service principal.

### Setting the GitHub Secret

After creating the service principal, add the entire JSON output to GitHub:

**Via GitHub Web UI:**
1. Navigate to your repository on GitHub
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `AZURE_CREDENTIALS`
5. Value: Paste the entire JSON output from the command above
6. Click **Add secret**

**Via GitHub CLI:**
```bash
# Copy the JSON output to a file temporarily
cat > /tmp/azure-credentials.json << 'EOF'
{
  "clientId": "xxxx",
  "clientSecret": "xxxx",
  ...
}
EOF

# Set the secret using gh CLI
gh secret set AZURE_CREDENTIALS < /tmp/azure-credentials.json

# Clean up
rm /tmp/azure-credentials.json
```

## 2. Function App Publish Profile (AZURE_FUNCTIONAPP_PUBLISH_PROFILE)

The Function App publish profile contains credentials for directly publishing to your Function App.

### Retrieving the Publish Profile

```bash
# Set your Function App name and resource group
FUNCTION_APP_NAME="your-function-app-name"
RESOURCE_GROUP="wireguard-spa-rg"

# Get the publish profile (XML format)
az functionapp deployment list-publishing-profiles \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --xml
```

**Alternatively**, use the helper script provided in this repository:

```bash
# Make the script executable
chmod +x scripts/get-function-publish-profile.sh

# Run the script
./scripts/get-function-publish-profile.sh $FUNCTION_APP_NAME $RESOURCE_GROUP

# Pipe directly to GitHub secret (if using gh CLI)
./scripts/get-function-publish-profile.sh $FUNCTION_APP_NAME $RESOURCE_GROUP | \
  gh secret set AZURE_FUNCTIONAPP_PUBLISH_PROFILE
```

### Setting the GitHub Secret

**Via GitHub Web UI:**
1. Copy the entire XML output from the command above
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`
5. Value: Paste the XML content
6. Click **Add secret**

**Via GitHub CLI:**
```bash
# Save to temporary file
az functionapp deployment list-publishing-profiles \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --xml > /tmp/publish-profile.xml

# Set the secret
gh secret set AZURE_FUNCTIONAPP_PUBLISH_PROFILE < /tmp/publish-profile.xml

# Clean up
rm /tmp/publish-profile.xml
```

## 3. Static Web App Deployment Token (AZURE_STATIC_WEB_APPS_API_TOKEN)

The deployment token is required for deploying to Azure Static Web Apps.

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

## 4. Function App Name (AZURE_FUNCTIONAPP_NAME)

This is simply the name of your Azure Function App resource.

### Finding Your Function App Name

```bash
# List all Function Apps in your resource group
az functionapp list \
  --resource-group wireguard-spa-rg \
  --query '[].name' -o tsv

# Or get it from the infrastructure deployment output
az deployment group show \
  --resource-group wireguard-spa-rg \
  --name main \
  --query 'properties.outputs.functionAppName.value' -o tsv
```

### Setting the GitHub Secret

**Via GitHub Web UI:**
1. Copy your Function App name
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `AZURE_FUNCTIONAPP_NAME`
5. Value: Paste your Function App name (e.g., `wgspa-func-abc123`)
6. Click **Add secret**

**Via GitHub CLI:**
```bash
# Replace with your actual Function App name
gh secret set AZURE_FUNCTIONAPP_NAME -b "your-function-app-name"
```

## 5. Managed Identity Role Assignments

Your Function App needs permissions to create and manage VMs for the WireGuard servers. The recommended approach is to use a system-assigned managed identity.

### Enable System-Assigned Managed Identity

```bash
# Set your Function App name and resource group
FUNCTION_APP_NAME="your-function-app-name"
RESOURCE_GROUP="wireguard-spa-rg"

# Enable system-assigned managed identity
az functionapp identity assign \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### Assign Required Roles

The Function App's managed identity needs the following roles to provision VMs:

#### Get the Managed Identity Principal ID

```bash
# Get the principal ID of the managed identity
PRINCIPAL_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

echo "Managed Identity Principal ID: $PRINCIPAL_ID"
```

#### Assign Virtual Machine Contributor Role

```bash
# Set subscription ID and resource group scope
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

# Assign Virtual Machine Contributor role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Virtual Machine Contributor" \
  --scope $SCOPE

echo "Assigned Virtual Machine Contributor role"
```

#### Assign Network Contributor Role

```bash
# Assign Network Contributor role for VNet/NIC management
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Network Contributor" \
  --scope $SCOPE

echo "Assigned Network Contributor role"
```

#### Alternative: Assign Contributor Role (Simpler but Broader)

If you prefer a simpler setup with broader permissions:

```bash
# Assign Contributor role (can do everything in the resource group)
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Contributor" \
  --scope $SCOPE

echo "Assigned Contributor role"
```

### Verify Role Assignments

```bash
# List all role assignments for the managed identity
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --output table

# Should show Virtual Machine Contributor and Network Contributor
# (or just Contributor if using that approach)
```

## 6. Alternative: OIDC/Federated Credentials

For enhanced security, you can use OpenID Connect (OIDC) with federated credentials instead of long-lived secrets. This eliminates the need to store `AZURE_CREDENTIALS` as a secret.

### Prerequisites

- Azure CLI version 2.37.0 or later
- GitHub repository owner and name
- Azure subscription with permissions to create federated credentials

### Create an Azure AD Application

```bash
# Create an Azure AD application
APP_NAME="wireguard-spa-github-actions"
APP_ID=$(az ad app create --display-name $APP_NAME --query appId -o tsv)

echo "Application ID: $APP_ID"

# Create a service principal for the application
az ad sp create --id $APP_ID
```

### Configure Federated Credentials

```bash
# Set your GitHub repository details
GITHUB_ORG="your-github-username"
GITHUB_REPO="WireGuard-spa"
BRANCH="main"  # or your default branch

# Create federated credential for main branch
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "wireguard-spa-main-branch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'$GITHUB_ORG'/'$GITHUB_REPO':ref:refs/heads/'$BRANCH'",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Optionally, create credentials for pull requests
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "wireguard-spa-pull-requests",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'$GITHUB_ORG'/'$GITHUB_REPO':pull_request",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### Assign Azure Roles to the Service Principal

```bash
# Get the service principal object ID
SP_OBJECT_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Assign Contributor role
az role assignment create \
  --assignee $APP_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID
```

### Configure GitHub Secrets for OIDC

Instead of `AZURE_CREDENTIALS`, set these three secrets:

```bash
# Get tenant ID
TENANT_ID=$(az account show --query tenantId -o tsv)

# Set secrets via gh CLI
gh secret set AZURE_CLIENT_ID -b "$APP_ID"
gh secret set AZURE_TENANT_ID -b "$TENANT_ID"
gh secret set AZURE_SUBSCRIPTION_ID -b "$SUBSCRIPTION_ID"
```

**Via GitHub Web UI:**
1. Navigate to **Settings** → **Secrets and variables** → **Actions**
2. Create three secrets:
   - `AZURE_CLIENT_ID`: The application ID
   - `AZURE_TENANT_ID`: Your Azure tenant ID
   - `AZURE_SUBSCRIPTION_ID`: Your subscription ID

### Update Workflow to Use OIDC

In your workflow files, replace the Azure Login step:

```yaml
# OLD (using AZURE_CREDENTIALS)
- name: Azure Login
  uses: azure/login@v1
  with:
    creds: ${{ secrets.AZURE_CREDENTIALS }}

# NEW (using OIDC)
- name: Azure Login
  uses: azure/login@v1
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

### Resources

- [Azure AD Workload Identity Federation](https://docs.microsoft.com/azure/active-directory/workload-identities/workload-identity-federation)
- [GitHub Actions: Azure Login with OIDC](https://github.com/marketplace/actions/azure-login#login-with-openid-connect-oidc-recommended)
- [Configuring OpenID Connect in Azure](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)

## Verification Checklist

Before running your deployment workflows, verify that everything is configured correctly:

### 1. Verify GitHub Secrets

Run the validate-secrets workflow:
```bash
# Via GitHub CLI
gh workflow run validate-secrets.yml

# Via GitHub Web UI
# Navigate to Actions → Validate Secrets → Run workflow
```

### 2. Verify Service Principal

```bash
# List service principals (find yours by name)
az ad sp list --display-name "wireguard-spa-deployer" --query '[].{Name:displayName, AppId:appId}' -o table

# Verify role assignments for the service principal
APP_ID=$(az ad sp list --display-name "wireguard-spa-deployer" --query '[0].appId' -o tsv)
az role assignment list --assignee $APP_ID --output table
```

### 3. Verify Function App Configuration

```bash
# Check if managed identity is enabled
az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP

# Verify Function App settings
az functionapp config appsettings list \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --output table

# Check Function App status
az functionapp show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query '{Name:name, State:state, DefaultHostName:defaultHostName}' -o table
```

### 4. Verify Static Web App

```bash
# Check Static Web App details
az staticwebapp show \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --query '{Name:name, DefaultHostname:defaultHostname, RepositoryUrl:repositoryUrl}' -o table

# Verify the deployment token exists (should show the first few characters)
az staticwebapp secrets list \
  --name $SWA_NAME \
  --resource-group $RESOURCE_GROUP \
  --query 'properties.apiKey' -o tsv | head -c 20 && echo "..."
```

### 5. Verify Role Assignments for Managed Identity

```bash
# Get managed identity principal ID
PRINCIPAL_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

# List all role assignments
az role assignment list \
  --assignee $PRINCIPAL_ID \
  --output table

# Expected roles: Virtual Machine Contributor and Network Contributor
# (or Contributor if using the simpler approach)
```

### Final Checklist

- [ ] GitHub secret `AZURE_CREDENTIALS` is set (or OIDC credentials if using federated auth)
- [ ] GitHub secret `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` is set
- [ ] GitHub secret `AZURE_STATIC_WEB_APPS_API_TOKEN` is set
- [ ] GitHub secret `AZURE_FUNCTIONAPP_NAME` is set
- [ ] Function App has system-assigned managed identity enabled
- [ ] Managed identity has Virtual Machine Contributor role assigned
- [ ] Managed identity has Network Contributor role assigned
- [ ] Service Principal has appropriate role on subscription or resource group
- [ ] All Azure resources are in the same resource group
- [ ] Function App application settings are configured correctly
- [ ] Static Web App is linked to Function App as backend (if applicable)

## Troubleshooting

### Secret Not Found Errors

If workflows fail with "secret not found" errors:
1. Verify the secret name is exactly as specified (case-sensitive)
2. Check that the secret is set at the repository level, not organization level
3. Ensure you have the correct permissions to view/edit secrets

### Permission Denied Errors

If you get permission errors during deployment:
1. Verify the service principal has the correct role assigned
2. Check the scope of the role assignment (subscription vs resource group)
3. Ensure the managed identity has been assigned roles
4. Wait a few minutes for role assignments to propagate

### Function App Deployment Fails

If Function App deployment fails:
1. Verify the publish profile is valid and not expired
2. Check Function App logs in Azure Portal
3. Ensure the Function App is running
4. Verify Python runtime version matches (3.10)

### Static Web App Deployment Fails

If Static Web App deployment fails:
1. Verify the deployment token is valid
2. Check that the app location and output location are correct
3. Ensure the Static Web App resource exists in Azure

## Next Steps

After completing this setup:

1. **Run the validation workflow** to verify all secrets are in place:
   ```bash
   gh workflow run validate-secrets.yml
   ```

2. **Test the infrastructure workflow** with DRY_RUN mode:
   - Ensure `DRY_RUN=true` is set in Function App settings
   - Run the infrastructure provisioning workflow
   - Verify deployment succeeds without creating actual VMs

3. **Configure authentication** in your Static Web App:
   - Add Google and/or Microsoft identity providers
   - Update the allowlist in Function App settings

4. **Enable production mode** when ready:
   - Set `DRY_RUN=false` in Function App settings
   - Test with actual VM provisioning
   - Monitor costs and usage

For more information, see the [README.md](README.md) and [DEPLOYMENT_FIX.md](DEPLOYMENT_FIX.md) files.
