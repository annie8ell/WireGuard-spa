# Quick Setup Guide: Automated Credentials Configuration for GitHub Codespaces

This guide provides a streamlined, automated approach to set up all required GitHub secrets and Azure permissions for the WireGuard SPA deployment from GitHub Codespaces (ideal for iPad or browser-based workflows).

## Overview

This guide provides automation scripts that:
- Install required CLI tools (Azure CLI, GitHub CLI)
- Discover your existing Azure infrastructure
- Automatically configure Azure permissions and roles
- Set up all GitHub repository secrets
- Validate the configuration

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

### Step 2: Authenticate to Azure

Authenticate to Azure (GitHub authentication is already configured in Codespaces):

```bash
# Login to Azure (this will open a browser)
az login

# Select your subscription (if you have multiple)
az account list --output table
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify you're logged in
az account show
```

**Note:** GitHub authentication is pre-configured in Codespaces via the `GITHUB_TOKEN` environment variable. You can verify with:
```bash
gh auth status
```

If you see "value of the gh token variable is being used" - that's normal and expected in Codespaces. You're already authenticated and ready to go.

### Step 3: Run Automated Setup

Now run the main setup script that does everything automatically:

```bash
# Make the script executable
chmod +x scripts/setup-all-secrets.sh

# Run the setup script
./scripts/setup-all-secrets.sh

# The script will:
# 1. Discover your Azure resources (Function App, Static Web App, Resource Group)
# 2. Create/verify the Service Principal with appropriate permissions
# 3. Enable and configure the Function App managed identity with required roles
# 4. Retrieve all necessary tokens and credentials
# 5. Set all GitHub repository secrets automatically
# 6. Validate the configuration
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

### GitHub Repository Secrets

| Secret Name | Description |
|------------|-------------|
| `AZURE_CREDENTIALS` | Service Principal credentials (JSON format) |
| `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` | Function App publish profile (XML) |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Static Web App deployment token |
| `AZURE_FUNCTIONAPP_NAME` | Name of your Function App |

### Azure Permissions

The script automatically configures:

1. **Service Principal** with Contributor role on your resource group
2. **Function App Managed Identity** enabled with:
   - Virtual Machine Contributor role
   - Network Contributor role

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
# Check GitHub secrets (doesn't show values, just confirms they exist)
gh secret list

# Check Azure Service Principal
az ad sp list --display-name "wireguard-spa-deployer" --query '[].{Name:displayName, AppId:appId}' -o table

# Check Function App managed identity and roles
FUNCTION_APP_NAME=$(az functionapp list --query '[0].name' -o tsv)
az functionapp identity show --name $FUNCTION_APP_NAME --resource-group <YOUR_RG> --query principalId -o tsv
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

### GitHub Authentication

GitHub authentication is pre-configured in Codespaces. If you see "value of the gh token variable is being used" - that's expected:

```bash
# Verify you're authenticated (should show your GitHub account)
gh auth status

# The GITHUB_TOKEN environment variable is pre-configured in Codespaces
```

If you need to use a different GitHub account:
```bash
# Unset the pre-configured token
unset GITHUB_TOKEN

# Login with a different account
gh auth logout
gh auth login
```

### Script Hangs or Times Out

If the script seems stuck:

1. Press `Ctrl+C` to cancel
2. Run with `--dry-run` to see what would be done
3. Check your network connection
4. Try running in non-interactive mode: `./scripts/setup-all-secrets.sh --non-interactive`

## Manual Setup Alternative

If you prefer manual setup or the automated script doesn't work for your scenario, see the detailed manual instructions in [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md).

The automated setup script (`setup-all-secrets.sh`) leverages the existing helper scripts:
- `get-function-publish-profile.sh` - For retrieving Function App credentials
- `get-swa-deploy-token.sh` - For retrieving Static Web App token

This ensures consistency between automated and manual approaches. You can also use these helper scripts individually if you only need to update specific secrets.

## What's Next?

After completing this setup:

1. **Provision Infrastructure** (if not already done):
   ```bash
   gh workflow run infra-provision-and-deploy.yml
   ```

2. **Deploy the Application**:
   ```bash
   # Deploy backend
   gh workflow run deploy-backend.yml
   
   # Deploy frontend
   gh workflow run deploy-frontend.yml
   ```

3. **Configure Authentication** in your Static Web App:
   - Navigate to Azure Portal → Your Static Web App → Authentication
   - Add Google and/or Microsoft identity providers

4. **Test with DRY_RUN mode first**:
   - The infrastructure workflow sets `DRY_RUN=true` by default
   - Test the complete flow without creating actual VMs
   - When ready, set `DRY_RUN=false` in Function App settings

## Security Considerations

The automated setup script:
- Creates a Service Principal with Contributor role (resource group scoped by default)
- Stores credentials securely as GitHub secrets
- Uses managed identities where possible
- Does not log sensitive information
- Provides options to review changes before applying (dry-run mode)

For production environments, consider:
- Using OIDC/federated credentials instead of Service Principal secrets
- Restricting Service Principal permissions to specific resources
- Regularly rotating credentials
- Using Azure Key Vault for additional secret management

See [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md) section 6 for OIDC setup instructions.

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section above
- Review [SETUP-SECRETS-AND-ROLES.md](SETUP-SECRETS-AND-ROLES.md) for detailed manual instructions
- Open a GitHub issue with error messages and logs

## Files in This Setup

- `SETUP-CREDENTIALS.md` (this file) - Quick automated setup guide
- `scripts/install-tools.sh` - Installs Azure CLI and GitHub CLI
- `scripts/setup-all-secrets.sh` - Main automated setup script (uses helper scripts below)
- `scripts/get-function-publish-profile.sh` - Helper script for Function App credentials (used by automated script)
- `scripts/get-swa-deploy-token.sh` - Helper script for SWA token (used by automated script)
- `.github/workflows/validate-secrets.yml` - Secrets validation workflow
- `SETUP-SECRETS-AND-ROLES.md` - Detailed manual setup instructions

**Note:** The automated setup script reuses the existing helper scripts to ensure consistency between automated and manual approaches.
