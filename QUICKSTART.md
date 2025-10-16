# Quick Start Guide

Get WireGuard SPA up and running in 15 minutes!

## Prerequisites

- Azure subscription
- GitHub account
- 15 minutes ⏱️

## Step 1: Fork Repository (30 seconds)

1. Click **Fork** button on GitHub
2. Clone your fork locally (optional)

## Step 2: Setup Azure Service Principal (3 minutes)

```bash
# Login to Azure
az login

# Create Service Principal
az ad sp create-for-rbac \
  --name "wireguard-spa-sp" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID \
  --sdk-auth
```

Copy the entire JSON output.

## Step 3: Configure GitHub Secrets (2 minutes)

1. Go to your forked repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `AZURE_CREDENTIALS`
4. Value: Paste the Service Principal JSON
5. Click **Add secret**

## Step 4: Deploy Everything (10 minutes)

1. Go to **Actions** tab
2. Select **Provision Infrastructure and Deploy** workflow
3. Click **Run workflow**
4. Use default values:
   - Resource Group: `wireguard-spa-rg`
   - Location: `eastus`
   - Project Name: `wgspa`
5. Click **Run workflow** button
6. ☕ Wait 8-10 minutes

## Step 5: Configure Authentication (3 minutes)

### For Microsoft Authentication (Easiest)

1. Open Azure Portal
2. Find your Static Web App (search for `wgspa-swa`)
3. Go to **Authentication** → **Add provider**
4. Select **Microsoft**
5. Choose **Express** configuration
6. Click **Add**

### For Google Authentication

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials
3. Add redirect URI: `https://YOUR-SWA-NAME.azurestaticapps.net/.auth/login/google/callback`
4. Copy Client ID and Secret
5. In Azure Portal → SWA → **Authentication** → Add Google provider
6. Paste credentials

## Step 6: Update Allowed Users (2 minutes)

1. In Azure Portal, find your Function App (search for `wgspa-func`)
2. Go to **Configuration**
3. Edit `ALLOWED_EMAILS` setting
4. Add your email(s): `your-email@example.com,another@example.com`
5. Click **Save**

## Step 7: Test It! (2 minutes)

1. Open your Static Web App URL (from workflow summary or Azure Portal)
2. Click **Sign in with Microsoft** (or Google)
3. Sign in with an allowed email
4. Click **Start Session**
5. Watch the magic happen! ✨

## What You Just Created

✅ Frontend SPA with authentication  
✅ Backend API with durable functions  
✅ Infrastructure as code (Bicep)  
✅ CI/CD pipeline (GitHub Actions)  
✅ Ephemeral VM provisioning  
✅ Monitoring (Application Insights)  

## URLs to Bookmark

- **Static Web App**: `https://YOUR-SWA-NAME.azurestaticapps.net`
- **Function App**: `https://YOUR-FUNC-NAME.azurewebsites.net`
- **Azure Portal**: `https://portal.azure.com`

## Common Issues

### Can't sign in?
- Check authentication provider is configured
- Verify your email is in `ALLOWED_EMAILS`

### VM not starting?
- Check Function App logs in Application Insights
- Try dry-run mode first: Set `DRY_RUN=true` in Function App config

### Deployment failed?
- Check GitHub Actions logs for errors
- Verify `AZURE_CREDENTIALS` secret is correct
- Ensure you have Contributor role on subscription

## Next Steps

📖 Read [SETUP.md](SETUP.md) for detailed configuration  
📖 Read [README.md](README.md) for full documentation  
📖 Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design  
🚀 Customize and extend the solution!

## Clean Up (When Done Testing)

```bash
az group delete --name wireguard-spa-rg --yes --no-wait
```

This deletes all resources and stops billing.

## Cost Estimate

💰 **Expected Monthly Cost**: $10-30  
(Most services are free tier or consumption-based)

- Static Web App: **Free**
- Function App: ~$5-15 (based on usage)
- Application Insights: ~$2-5
- Storage: ~$1-3
- VMs: $0.01-0.02 per hour per session

## Support

Need help? Check:
- 📚 [Documentation](README.md)
- 🏗️ [Architecture Guide](ARCHITECTURE.md)
- 🤝 [Contributing Guide](CONTRIBUTING.md)
- 💬 Open an issue on GitHub

---

**Congratulations!** 🎉 You now have a fully functional WireGuard VPN service running on Azure!
