# WireGuard SPA - Quick Setup Guide

This guide will help you deploy the WireGuard SPA solution from scratch.

> **Setup Documentation**: For automated credential configuration, see [SETUP-CREDENTIALS.md](SETUP-CREDENTIALS.md). For manual secrets & RBAC setup, see [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md).

## Step 1: Prerequisites

### Required Azure Resources
- Azure Subscription with Contributor permissions
- Azure CLI installed locally (optional, for manual deployment)

### Required GitHub Secret

Create this secret in your GitHub repository (Settings → Secrets and variables → Actions):

#### AZURE_STATIC_WEB_APPS_API_TOKEN

Deployment token for Azure Static Web Apps.

```bash
# Get the deployment token from your Static Web App
az staticwebapp secrets list \
  --name <your-swa-name> \
  --resource-group <resource-group-name> \
  --query 'properties.apiKey' -o tsv
```

Copy the token and save it as `AZURE_STATIC_WEB_APPS_API_TOKEN` secret.

## Step 2: Create Azure Static Web App

### Option A: Using Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Click **Create a resource** → **Static Web App**
3. Configure:
   - **Resource Group**: Create new or use existing
   - **Name**: `wireguard-spa`
   - **Plan type**: Free
   - **Region**: Choose your preferred region
   - **Deployment details**: Select "Other" (we'll deploy via GitHub Actions)
4. Click **Review + create** → **Create**

### Option B: Using Azure CLI

```bash
# Login to Azure
az login

# Create resource group
az group create \
  --name wireguard-spa-rg \
  --location eastus

# Create Static Web App
az staticwebapp create \
  --name wireguard-spa \
  --resource-group wireguard-spa-rg \
  --location eastus \
  --sku Free
```

## Step 3: Deploy Application

### Deploy via GitHub Actions (Recommended)

```bash
# Get the deployment token
az staticwebapp secrets list \
  --name wireguard-spa \
  --resource-group wireguard-spa-rg \
  --query 'properties.apiKey' -o tsv

# Set as GitHub secret (see Step 1)
gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN

# Push to main branch or manually trigger workflow
gh workflow run azure-static-web-apps.yml
SWA_TOKEN=$(az staticwebapp secrets list \
  --name <swa-name> \
  --resource-group wireguard-spa-rg \
  --query 'properties.apiKey' -o tsv)

# Deploy using Static Web Apps CLI
npm install -g @azure/static-web-apps-cli
swa deploy ./dist --deployment-token $SWA_TOKEN
```

Or use the **Deploy Frontend** workflow in GitHub Actions.

## Step 4: Configure SWA App Settings

Configure Service Principal credentials for VM provisioning:

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to your Static Web App resource
3. Click **Configuration** → **Application settings**
4. Add the following settings:
   - `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID
   - `AZURE_RESOURCE_GROUP`: Resource group where VMs will be created
   - `AZURE_CLIENT_ID`: Service Principal application ID
   - `AZURE_CLIENT_SECRET`: Service Principal secret
   - `AZURE_TENANT_ID`: Azure AD tenant ID
   - `DRY_RUN`: Set to `true` for testing (no real VMs created)
5. Click **Save**

To create the Service Principal:
```bash
az ad sp create-for-rbac \
  --name "wireguard-spa-vm-provisioner" \
  --role "Virtual Machine Contributor" \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>
```

## Step 5: Configure Authentication Providers

The SPA supports Google and Microsoft authentication.

#### Configure Google Authentication

1. In Azure Portal, go to your Static Web App
2. Click **Authentication** in the left menu
3. Click **+ Add provider**
4. Select **Google**
5. You'll need:
   - **Client ID** from Google Cloud Console
   - **Client Secret** from Google Cloud Console
6. To get these:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a project (if needed)
   - Enable Google+ API
   - Go to **APIs & Services** → **Credentials**
   - Create **OAuth 2.0 Client ID**
   - Add authorized redirect URIs:
     - `https://<your-swa-name>.azurestaticapps.net/.auth/login/google/callback`
   - Copy Client ID and Secret
7. Paste Client ID and Secret in Azure Portal
8. Click **Add**

#### Configure Microsoft (Azure AD) Authentication

1. In Azure Portal, go to your Static Web App
2. Click **Authentication** in the left menu
3. Click **+ Add provider**
4. Select **Microsoft**
5. Choose configuration method:
   - **Express**: Automatically create app registration
   - **Advanced**: Use existing app registration
6. For Express: Just click **Add**
7. For Advanced: You'll need App (client) ID and Client Secret from Azure AD App Registration

## Step 6: Configure User Roles

By default, only invited users with the 'invited' role are authorized:

1. Go to your Static Web App in Azure Portal
2. Click **Configuration** → **Role management**
3. Add users to the 'invited' role with their email addresses (e.g., `annie8ell@gmail.com` or `your-email@example.com`)
4. Users must sign in with these exact email addresses

> **Note**: Replace `your-email@example.com` with actual email addresses you want to allow.

## Step 7: Test the Application

1. Navigate to your Static Web App URL:
   ```
   https://<your-swa-name>.azurestaticapps.net
   ```
   
2. Click **Sign in with Google** or **Sign in with Microsoft**

3. Authenticate with an allowed email address

4. Once logged in, you should see:
   - Welcome message with your email
   - Option to start a VPN session
   - Duration selector

5. Click **Start Session** to create a WireGuard VM

6. The session info will show:
   - Instance ID
   - Status (starting → running → completed)
   - Public IP (when VM is ready)
   - Remaining time

## Step 8: Monitor and Troubleshoot

### View Logs

**SWA Function Logs:**
1. Go to Static Web App in Azure Portal
2. Click **Log stream** in the left menu
3. Or use Application Insights (if configured)

### Common Issues

#### "User not authorized" error
- Verify user is assigned to 'invited' role in SWA Role management
- Check SWA authentication configuration in Azure Portal

#### SWA deployment fails
- Verify `AZURE_STATIC_WEB_APPS_API_TOKEN` secret is correct
- Check GitHub Actions workflow logs for specific errors
- Ensure the Static Web App resource exists in Azure

#### VM provisioning fails
- Verify Service Principal credentials in SWA app settings
- Check Service Principal has VM Contributor role
- Verify `AZURE_RESOURCE_GROUP` exists and is accessible
- Try enabling dry-run mode first: set `DRY_RUN=true` in SWA app settings

### Enable Dry Run Mode

To test without creating actual VMs:

1. Go to Static Web App → Configuration → Application settings
2. Set `DRY_RUN` to `true`
3. Click **Save**
4. VMs won't be created, but you'll see the flow work end-to-end

## Step 9: Cost Optimization

### Monitor Costs
- Use Azure Cost Management to track spending
- Set up budget alerts

### Optimize Resources
- Use Free tier for Static Web App (upgrade to Standard only if needed)
- SWA built-in Functions are included (no separate Function App cost)
- Ensure VMs are destroyed after sessions (automatic 30-minute cleanup)
- Use smallest VM size (B1ls) unless you need more

### Clean Up Resources

To delete everything:
```bash
az group delete --name wireguard-spa-rg --yes --no-wait
```

## Next Steps

- Configure custom domain for Static Web App
- Set up monitoring alerts in Application Insights
- Adjust session duration limits
- Customize VM size and WireGuard configuration
- Add additional authentication providers
- Implement WireGuard configuration distribution

## Support

For issues or questions:
- Review the main [README.md](README.md)
- Check [Azure Static Web Apps documentation](https://docs.microsoft.com/azure/static-web-apps/)
- Check [MIGRATION.md](MIGRATION.md) for architecture details

## Security Best Practices

✅ **Do:**
- Use Service Principal with minimal required permissions
- Keep secrets in Azure Key Vault (optional enhancement)
- Review role assignments regularly
- Monitor authentication logs
- Keep allowed users list up to date
- Use HTTPS only (already configured)

❌ **Don't:**
- Commit secrets to source control
- Give Service Principal more permissions than needed
- Allow public access to API endpoints (use SWA auth with 'invited' role)
- Disable HTTPS
- Skip monitoring and logging
