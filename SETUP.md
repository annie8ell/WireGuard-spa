# WireGuard SPA - Quick Setup Guide

This guide will help you deploy the WireGuard SPA solution from scratch.

## Step 1: Prerequisites

### Required Azure Resources
- Azure Subscription with Contributor permissions
- Azure CLI installed locally (optional, for manual deployment)

### Required GitHub Secrets

Create these secrets in your GitHub repository (Settings → Secrets and variables → Actions):

#### 1. AZURE_CREDENTIALS (Required)

Service Principal JSON for infrastructure provisioning and SWA token retrieval.

```bash
# Create Service Principal with Contributor role
az ad sp create-for-rbac \
  --name "wireguard-spa-sp" \
  --role contributor \
  --scopes /subscriptions/{YOUR_SUBSCRIPTION_ID} \
  --sdk-auth
```

Copy the entire JSON output and save it as `AZURE_CREDENTIALS` secret.

#### 2. AZURE_FUNCTIONAPP_PUBLISH_PROFILE (Optional)

Publish profile for Azure Functions deployment. You can skip this if you prefer to retrieve it dynamically in the workflow.

To get the publish profile after infrastructure deployment:
```bash
az functionapp deployment list-publishing-profiles \
  --name <function-app-name> \
  --resource-group <resource-group-name> \
  --xml
```

Save the XML output as `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` secret.

## Step 2: Deploy Infrastructure and Code

### Option A: One-Click Deployment (Recommended)

1. Go to **Actions** → **Provision Infrastructure and Deploy**
2. Click **Run workflow**
3. Fill in the parameters:
   - **Resource Group Name**: `wireguard-spa-rg` (or your preference)
   - **Location**: `eastus` (or your preferred Azure region)
   - **Project Name**: `wgspa` (short prefix for resource names, lowercase)
4. Click **Run workflow**
5. Wait ~10-15 minutes for completion

### Option B: Manual Deployment

#### Step 2.1: Deploy Infrastructure

```bash
# Login to Azure
az login

# Create resource group
az group create \
  --name wireguard-spa-rg \
  --location eastus

# Deploy Bicep template
az deployment group create \
  --resource-group wireguard-spa-rg \
  --template-file infra/main.bicep \
  --parameters projectName=wgspa
```

Save the outputs from the deployment - you'll need them for the next steps.

#### Step 2.2: Deploy Backend

```bash
cd backend
pip install -r requirements.txt

# Deploy using Azure Functions Core Tools
func azure functionapp publish <function-app-name>
```

Or use the **Deploy Backend** workflow in GitHub Actions.

#### Step 2.3: Deploy Frontend

```bash
cd frontend
npm install
npm run build

# Get SWA deployment token
SWA_TOKEN=$(az staticwebapp secrets list \
  --name <swa-name> \
  --resource-group wireguard-spa-rg \
  --query 'properties.apiKey' -o tsv)

# Deploy using Static Web Apps CLI
npm install -g @azure/static-web-apps-cli
swa deploy ./dist --deployment-token $SWA_TOKEN
```

Or use the **Deploy Frontend** workflow in GitHub Actions.

## Step 3: Post-Deployment Configuration

### 3.1 Link Function App as Backend

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to your Static Web App resource
3. In the left menu, click **Backends**
4. Click **+ Add**
5. Configure:
   - **Backend resource type**: Function App
   - **Subscription**: (select your subscription)
   - **Resource**: (select your Function App)
   - **Backend name**: `api`
6. Click **Link**
7. Wait for the configuration to propagate (~2-5 minutes)

### 3.2 Configure Authentication Providers

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

### 3.3 Update Allowed Users

By default, only these users are authorized:
- awwsawws@gmail.com
- awwsawws@hotmail.com

To allow different users:

1. Go to your Function App in Azure Portal
2. Click **Configuration** in the left menu
3. Find the `ALLOWED_EMAILS` app setting
4. Click **Edit**
5. Update the value with comma-separated email addresses
6. Click **OK** and **Save**

Or redeploy infrastructure with custom `allowedEmails` parameter:
```bash
az deployment group create \
  --resource-group wireguard-spa-rg \
  --template-file infra/main.bicep \
  --parameters projectName=wgspa \
  --parameters allowedEmails="user1@example.com,user2@example.com"
```

## Step 4: Test the Application

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

## Step 5: Monitor and Troubleshoot

### View Logs

**Function App Logs:**
1. Go to Function App in Azure Portal
2. Click **Log stream** in the left menu
3. Or use Application Insights for detailed logs

**Static Web App Logs:**
1. Go to Static Web App in Azure Portal
2. Click **Application Insights** (if configured)

### Common Issues

#### "User not authorized" error
- Verify your email is in the `ALLOWED_EMAILS` list
- Check Function App configuration in Azure Portal

#### SWA deployment fails
- Verify `AZURE_CREDENTIALS` secret has correct permissions
- Check workflow logs for specific errors
- Ensure build output location matches `dist`

#### Function App deployment fails
- Verify `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` secret is set
- Check Python version matches (3.9)
- Review Function App logs

#### VM provisioning fails
- Verify Function App Managed Identity has role assignments
- Check Function App logs in Application Insights
- Try enabling dry-run mode first: set `DRY_RUN=true` in Function App settings

### Enable Dry Run Mode

To test orchestration without creating actual VMs:

1. Go to Function App → Configuration
2. Set `DRY_RUN` to `true`
3. Save and restart Function App
4. VMs won't be created, but you'll see logs as if they were

## Step 6: Cost Optimization

### Monitor Costs
- Use Azure Cost Management to track spending
- Set up budget alerts

### Optimize Resources
- Use Free tier for Static Web App (upgrade to Standard only if needed)
- Consumption plan for Function App (pay per execution)
- Ensure VMs are destroyed after sessions (check `DRY_RUN=false`)
- Use smallest VM size (B1s) unless you need more

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
- Check [Azure Functions documentation](https://docs.microsoft.com/azure/azure-functions/)
- Check [Azure Durable Functions documentation](https://docs.microsoft.com/azure/azure-functions/durable/)

## Security Best Practices

✅ **Do:**
- Use Managed Identities (already configured)
- Keep secrets in Azure Key Vault (optional enhancement)
- Review role assignments regularly
- Monitor authentication logs
- Keep allowed users list up to date
- Use HTTPS only (already configured)

❌ **Don't:**
- Commit secrets to source control
- Give Function App more permissions than needed
- Allow public access to Function endpoints (use SWA auth)
- Disable HTTPS
- Skip monitoring and logging
