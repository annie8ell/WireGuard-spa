# Quick Setup Guide: Automated Credentials Configuration for GitHub Codespaces

This guide provides a streamlined, automated approach to set up all required GitHub secrets and Azure permissions for the WireGuard SPA deployment from GitHub Codespaces (ideal for iPad or browser-based workflows).

> **Setup Path**: This guide covers the **automated** credentials configuration approach. If you prefer manual setup or need more control, see [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md) for detailed manual instructions.

## Overview

This guide provides automation scripts that:
- Install required CLI tools (Azure CLI, GitHub CLI)
- Discover your existing Azure infrastructure
- Automatically configure Azure permissions and roles
- Set up all GitHub repository secrets
- Validate the configuration

## Important: GitHub Authentication in Codespaces

⚠️ **The default `GITHUB_TOKEN` in Codespaces has read-only access and cannot manage repository secrets.** You must authenticate with full permissions using device code flow (`gh auth login --web`). Don't worry - you can restore the original token after setup is complete.

## Quick Start (3-Step Process for Codespaces)

### Step 1: Install Required Tools

In your Codespace terminal, run:

```bash
chmod +x scripts/install-tools.sh
./scripts/install-tools.sh
```

**What this installs:**
- Azure CLI (`az`)
- GitHub CLI (`gh`)
- Required dependencies (curl, jq, etc.)

### Step 2: Authenticate to Azure and GitHub

#### Authenticate to Azure

```bash
# Login to Azure (this will open a browser)
az login

# Select your subscription (if you have multiple)
az account list --output table
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify you're logged in
az account show
```

#### Authenticate to GitHub (with secrets management permissions)

The default `GITHUB_TOKEN` in Codespaces has read-only access and **cannot manage repository secrets**. You need to login with proper credentials:

```bash
# Save the original token (to restore later)
export ORIGINAL_GITHUB_TOKEN="$GITHUB_TOKEN"

# Unset the read-only token
unset GITHUB_TOKEN

# Login with device code flow (provides full access)
gh auth login --web

# Verify you have the right permissions
gh auth status
```

**After running the setup script** (Step 3), you can restore the original token:
```bash
# Restore the original Codespaces token
export GITHUB_TOKEN="$ORIGINAL_GITHUB_TOKEN"

# Verify restoration
gh auth status
```

### Step 3: Run Automated Setup

**Important:** Ensure you've authenticated with `gh auth login --web` (Step 2) before running this script, as it needs permissions to manage repository secrets.

Now run the main setup script that does everything automatically:

```bash
# Make the script executable
chmod +x scripts/setup-all-secrets.sh

# Run the setup script
./scripts/setup-all-secrets.sh

# The script will:
# 1. Discover your Azure resources (Static Web App, Resource Group)
# 2. Create/verify the Service Principal with appropriate permissions for VM provisioning
# 3. Retrieve the Static Web App deployment token
# 4. Set GitHub repository secret automatically
# 5. Validate the configuration
```

#### Script Options

The setup script supports several options for flexibility:

```bash
# Interactive mode (default) - prompts for confirmation
./scripts/setup-all-secrets.sh

# Non-interactive mode - uses defaults or discovered values
./scripts/setup-all-secrets.sh --non-interactive

# Specify resource group explicitly
./scripts/setup-all-secrets.sh --resource-group wireguard-spa-rg

# Override/force update existing secrets
./scripts/setup-all-secrets.sh --force

# Dry run - show what would be done without making changes
./scripts/setup-all-secrets.sh --dry-run

# Get help
./scripts/setup-all-secrets.sh --help
```

## What Gets Configured

The automated setup script configures the following:

### GitHub Repository Secret

| Secret Name | Description |
|------------|-------------|
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Static Web App deployment token |

> **Note**: With the current SWA built-in Functions architecture, only the SWA deployment token is needed for GitHub Actions. The Service Principal credentials for VM provisioning are configured as **SWA app settings** (not GitHub secrets).

### Azure Permissions

The script automatically configures:

1. **Service Principal** with VM Contributor role on your resource group (configured as SWA app settings)

## Verification

After running the setup script, verify everything is configured:

```bash
# Run the validation workflow
gh workflow run validate-secrets.yml

# Check workflow status
gh run list --workflow=validate-secrets.yml --limit 1

# View the results
gh run view --web
```

Or manually verify:

```bash
# Check GitHub secret (doesn't show value, just confirms it exists)
gh secret list | grep AZURE_STATIC_WEB_APPS_API_TOKEN

# Check Azure Service Principal
az ad sp list --display-name "wireguard-spa-vm-provisioner" --query '[].{Name:displayName, AppId:appId}' -o table

# Check SWA app settings (Service Principal credentials)
SWA_NAME=$(az staticwebapp list --query '[0].name' -o tsv)
az staticwebapp appsettings list --name $SWA_NAME --resource-group <YOUR_RG> --output table
```

## Troubleshooting

### Script Fails to Find Azure Resources

If the script can't auto-discover your resources:

```bash
# List all resource groups
az group list --output table

# List resources in a specific group
az resource list --resource-group <RG_NAME> --output table

# Run script with explicit resource group
./scripts/setup-all-secrets.sh --resource-group <YOUR_RG_NAME>
```

### Permission Errors

If you get permission errors:

```bash
# Check your Azure role assignments
az role assignment list --assignee $(az account show --query user.name -o tsv) --output table

# You need at least Contributor role on the subscription or resource group
```

### GitHub Authentication and Secrets Management

**Important:** The default `GITHUB_TOKEN` in Codespaces has **read-only access** and cannot manage repository secrets. You must authenticate with full permissions.

#### Permission Denied Errors

If you get "permission denied" or "insufficient permissions" when setting secrets:

```bash
# The default GITHUB_TOKEN doesn't have secrets:write permission
# You need to authenticate with device code flow

# Save original token
export ORIGINAL_GITHUB_TOKEN="$GITHUB_TOKEN"

# Unset the read-only token
unset GITHUB_TOKEN

# Login with full permissions
gh auth login --web

# Verify - should show "Logged in to github.com as <your-username>"
gh auth status
```

#### Restoring the Original Token

After the setup is complete, restore the Codespaces token:

```bash
# Restore original token
export GITHUB_TOKEN="$ORIGINAL_GITHUB_TOKEN"

# Verify restoration
gh auth status
```

This allows you to continue using Codespaces normally after setup.

### Script Hangs or Times Out

If the script seems stuck:

1. Press `Ctrl+C` to cancel
2. Run with `--dry-run` to see what would be done
3. Check your network connection
4. Try running in non-interactive mode: `./scripts/setup-all-secrets.sh --non-interactive`

## Manual Setup Alternative

If you prefer manual setup or the automated script doesn't work for your scenario, see the detailed manual instructions in [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md).

The automated setup script (`setup-all-secrets.sh`) can leverage the existing helper script:
- `get-swa-deploy-token.sh` - For retrieving Static Web App token

## What's Next?

After completing this setup:

1. **Deploy the Application**:
   ```bash
   # Deploy via GitHub Actions
   gh workflow run azure-static-web-apps.yml
   
   # Or push to main branch
   git push origin main
   ```

2. **Configure SWA App Settings**:
   - Navigate to Azure Portal → Your Static Web App → Configuration
   - Add Service Principal credentials for VM provisioning:
     - `AZURE_SUBSCRIPTION_ID`
     - `AZURE_RESOURCE_GROUP`
     - `AZURE_CLIENT_ID`
     - `AZURE_CLIENT_SECRET`
     - `AZURE_TENANT_ID`
     - `DRY_RUN=true` (for testing)

3. **Configure Authentication** in your Static Web App:
   - Navigate to Azure Portal → Your Static Web App → Authentication
   - Add Google and/or Microsoft identity providers
   - Assign users to 'invited' role in Role management

4. **Test with DRY_RUN mode first**:
   - Set `DRY_RUN=true` in SWA app settings
   - Test the complete flow without creating actual VMs
   - When ready, set `DRY_RUN=false`

## Security Considerations

The automated setup script:
- Creates a Service Principal with VM Contributor role (resource group scoped)
- Stores SWA deployment token securely as GitHub secret
- Service Principal credentials stored as SWA app settings (not GitHub secrets)
- Does not log sensitive information
- Provides options to review changes before applying (dry-run mode)

For production environments, consider:
- Restricting Service Principal permissions to specific resources
- Regularly rotating credentials
- Using Azure Key Vault for additional secret management

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section above
- Review [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md) for detailed manual instructions
- Open a GitHub issue with error messages and logs
