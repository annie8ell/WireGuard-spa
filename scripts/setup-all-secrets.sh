#!/bin/bash

##############################################################################
# Script: setup-all-secrets.sh
# Description: Automated setup of Azure permissions and GitHub secrets
# Usage: ./setup-all-secrets.sh [OPTIONS]
##############################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
RESOURCE_GROUP=""
NON_INTERACTIVE=false
FORCE=false
DRY_RUN=false
SP_NAME="wireguard-spa-deployer"

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Automated setup of Azure permissions and GitHub repository secrets for WireGuard SPA.

This script will:
1. Discover Azure resources (or use provided values)
2. Create/verify Service Principal with appropriate permissions
3. Enable Function App managed identity with required roles
4. Retrieve all necessary credentials
5. Set GitHub repository secrets automatically

Options:
  --resource-group <name>   Specify Azure resource group name
  --non-interactive         Run without prompts (use defaults/discovered values)
  --force                   Override existing secrets
  --dry-run                 Show what would be done without making changes
  --help, -h                Show this help message

Examples:
  # Interactive mode (default)
  $0

  # Non-interactive with specific resource group
  $0 --resource-group wireguard-spa-rg --non-interactive

  # Dry run to see what would happen
  $0 --dry-run

  # Force update existing secrets
  $0 --force

EOF
    exit 0
}

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking Prerequisites"
    
    local missing=false
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI (az) is not installed"
        log_info "Run: ./scripts/install-tools.sh"
        missing=true
    else
        # Query the azure-cli version value correctly (no extra escaped quotes)
        log_success "Azure CLI found: $(az version --query \"azure-cli\" -o tsv)"
    fi
    
    # Check GitHub CLI
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) is not installed"
        log_info "Run: ./scripts/install-tools.sh"
        missing=true
    else
        log_success "GitHub CLI found: $(gh --version | head -1)"
    fi
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed"
        missing=true
    else
        log_success "jq found"
    fi
    
    if [[ "$missing" == "true" ]]; then
        log_error "Missing required tools. Please install them first."
        exit 1
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure CLI"
        log_info "Run: az login"
        exit 1
    else
        local account_name=$(az account show --query name -o tsv)
        log_success "Logged in to Azure: $account_name"
    fi
    
    # Check GitHub login
    if ! gh auth status &> /dev/null; then
        log_error "Not authenticated to GitHub CLI"
        log_info "Run: gh auth login"
        exit 1
    else
        log_success "Authenticated to GitHub"
    fi
}

# Discover Azure resources
discover_resources() {
    log_step "Discovering Azure Resources"
    
    SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    log_info "Using subscription: $SUBSCRIPTION_ID"
    
    # Find resource group if not specified
    if [[ -z "$RESOURCE_GROUP" ]]; then
        log_info "Searching for resource groups..."
        
        # Look for common patterns
        local rgs=$(az group list --query "[?contains(name, 'wireguard') || contains(name, 'wg') || contains(name, 'spa')].name" -o tsv)
        
        if [[ -z "$rgs" ]]; then
            log_error "No resource groups found matching common patterns"
            log_info "Available resource groups:"
            az group list --query "[].name" -o tsv
            
            if [[ "$NON_INTERACTIVE" == "false" ]]; then
                echo -n "Enter resource group name: "
                read RESOURCE_GROUP
            else
                log_error "Use --resource-group to specify the resource group name"
                exit 1
            fi
        elif [[ $(echo "$rgs" | wc -l) -eq 1 ]]; then
            RESOURCE_GROUP="$rgs"
            log_success "Found resource group: $RESOURCE_GROUP"
        else
            log_warning "Multiple resource groups found:"
            echo "$rgs" | nl
            
            if [[ "$NON_INTERACTIVE" == "false" ]]; then
                echo -n "Select resource group number (or enter name): "
                read selection
                if [[ "$selection" =~ ^[0-9]+$ ]]; then
                    RESOURCE_GROUP=$(echo "$rgs" | sed -n "${selection}p")
                else
                    RESOURCE_GROUP="$selection"
                fi
            else
                RESOURCE_GROUP=$(echo "$rgs" | head -1)
                log_warning "Using first match: $RESOURCE_GROUP"
            fi
        fi
    fi
    
    log_info "Using resource group: $RESOURCE_GROUP"
    
    # Find Function App
    FUNCTION_APP_NAME=$(az functionapp list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)
    if [[ -z "$FUNCTION_APP_NAME" || "$FUNCTION_APP_NAME" == "null" ]]; then
        log_error "No Function App found in resource group: $RESOURCE_GROUP"
        exit 1
    fi
    log_success "Found Function App: $FUNCTION_APP_NAME"
    
    # Find Static Web App
    SWA_NAME=$(az staticwebapp list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)
    if [[ -z "$SWA_NAME" || "$SWA_NAME" == "null" ]]; then
        log_warning "No Static Web App found in resource group (this may be okay)"
        SWA_NAME=""
    else
        log_success "Found Static Web App: $SWA_NAME"
    fi
}

# Create or verify Service Principal
setup_service_principal() {
    log_step "Setting Up Service Principal"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create/verify Service Principal: $SP_NAME"
        return 0
    fi
    
    # Check if SP already exists
    SP_APP_ID=$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv)
    
    if [[ -n "$SP_APP_ID" && "$SP_APP_ID" != "null" ]]; then
        log_warning "Service Principal '$SP_NAME' already exists (AppId: $SP_APP_ID)"

        # If force is set, delete and recreate
        if [[ "$FORCE" == "true" ]]; then
            log_info "--force specified: deleting existing Service Principal to recreate..."
            az ad sp delete --id "$SP_APP_ID"
        else
            if [[ "$NON_INTERACTIVE" == "false" ]]; then
                echo -n "Recreate Service Principal? (y/N): "
                read recreate
                if [[ "$recreate" != "y" && "$recreate" != "Y" ]]; then
                    log_info "Using existing Service Principal"
                    # Existing SP - cannot retrieve secret. Create a new client secret if user agrees.
                    if [[ "$NON_INTERACTIVE" == "false" ]]; then
                        echo -n "Create a new client secret for the existing Service Principal? (y/N): "
                        read create_secret
                        if [[ "$create_secret" == "y" || "$create_secret" == "Y" ]]; then
                            log_info "Creating new client secret for existing Service Principal..."
                            # Create new credential
                            SP_CREDENTIALS=$(az ad sp credential reset --name "$SP_APP_ID" --query '{clientId:appId,clientSecret:password,tenantId:tenant}' -o json)
                            SP_APP_ID=$(echo "$SP_CREDENTIALS" | jq -r '.clientId')
                            log_success "Created new client secret for existing Service Principal"
                            return 0
                        else
                            log_error "Cannot proceed without Service Principal credentials. Rerun with --force to recreate the SP or create credentials manually."
                            exit 1
                        fi
                    else
                        log_error "Existing Service Principal found but no credentials available. Rerun with --force to recreate the SP or run interactively to create a new client secret."
                        exit 1
                    fi
                fi
            else
                log_info "Non-interactive mode: leaving existing Service Principal in place (use --force to recreate)"
                log_error "Cannot retrieve existing SP secret. Use --force to recreate or create credentials manually and set AZURE_CREDENTIALS as a GitHub secret."
                exit 1
            fi
        fi
    fi
    
    # Create new Service Principal
    log_info "Creating Service Principal with Contributor role on resource group..."
    
    local sp_output=$(az ad sp create-for-rbac \
        --name "$SP_NAME" \
        --role Contributor \
        --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
        --sdk-auth)
    
    # Store the full sdk-auth JSON for GitHub secret and extract the app id
    SP_CREDENTIALS="$sp_output"
    SP_APP_ID=$(echo "$sp_output" | jq -r '.clientId')
    
    log_success "Service Principal created: $SP_APP_ID"
}

# Enable and configure Function App managed identity
setup_managed_identity() {
    log_step "Configuring Function App Managed Identity"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would enable managed identity and assign roles for: $FUNCTION_APP_NAME"
        return 0
    fi
    
    # Enable system-assigned managed identity
    log_info "Enabling system-assigned managed identity..."
    az functionapp identity assign \
        --name "$FUNCTION_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output none
    
    # Get principal ID
    PRINCIPAL_ID=$(az functionapp identity show \
        --name "$FUNCTION_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query principalId -o tsv)
    
    log_success "Managed identity enabled: $PRINCIPAL_ID"
    
    # Assign roles
    local scope="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
    
    log_info "Assigning Virtual Machine Contributor role..."
    az role assignment create \
        --assignee "$PRINCIPAL_ID" \
        --role "Virtual Machine Contributor" \
        --scope "$scope" \
        --output none 2>/dev/null || log_warning "Role may already be assigned"
    
    log_info "Assigning Network Contributor role..."
    az role assignment create \
        --assignee "$PRINCIPAL_ID" \
        --role "Network Contributor" \
        --scope "$scope" \
        --output none 2>/dev/null || log_warning "Role may already be assigned"
    
    log_success "Roles assigned to managed identity"
}

# Retrieve Function App publish profile
get_function_publish_profile() {
    log_step "Retrieving Function App Publish Profile"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would retrieve publish profile for: $FUNCTION_APP_NAME"
        FUNCTION_PUBLISH_PROFILE="[DRY RUN - PLACEHOLDER]"
        return 0
    fi
    
    # Get the directory where this script is located
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local helper_script="$script_dir/get-function-publish-profile.sh"
    
    if [[ -f "$helper_script" ]]; then
        log_info "Using helper script to fetch publish profile..."
        FUNCTION_PUBLISH_PROFILE=$("$helper_script" "$FUNCTION_APP_NAME" "$RESOURCE_GROUP" 2>/dev/null)
        if [[ $? -eq 0 && -n "$FUNCTION_PUBLISH_PROFILE" ]]; then
            log_success "Publish profile retrieved via helper script"
            return 0
        else
            log_warning "Helper script failed, falling back to direct az command"
        fi
    fi
    
    # Fallback to direct az command if helper script not available or failed
    log_info "Fetching publish profile directly..."
    FUNCTION_PUBLISH_PROFILE=$(az functionapp deployment list-publishing-profiles \
        --name "$FUNCTION_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --xml)
    
    log_success "Publish profile retrieved"
}

# Retrieve Static Web App deployment token
get_swa_token() {
    log_step "Retrieving Static Web App Deployment Token"
    
    if [[ -z "$SWA_NAME" ]]; then
        log_warning "No Static Web App found - skipping token retrieval"
        SWA_TOKEN=""
        return 0
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would retrieve SWA token for: $SWA_NAME"
        SWA_TOKEN="[DRY RUN - PLACEHOLDER]"
        return 0
    fi
    
    # Get the directory where this script is located
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local helper_script="$script_dir/get-swa-deploy-token.sh"
    
    if [[ -f "$helper_script" ]]; then
        log_info "Using helper script to fetch SWA deployment token..."
        SWA_TOKEN=$("$helper_script" "$SWA_NAME" "$RESOURCE_GROUP" 2>/dev/null)
        if [[ $? -eq 0 && -n "$SWA_TOKEN" && "$SWA_TOKEN" != "null" ]]; then
            log_success "Deployment token retrieved via helper script"
            return 0
        else
            log_warning "Helper script failed, falling back to direct az command"
        fi
    fi
    
    # Fallback to direct az command if helper script not available or failed
    log_info "Fetching deployment token directly..."
    SWA_TOKEN=$(az staticwebapp secrets list \
        --name "$SWA_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.apiKey' -o tsv)
    
    log_success "Deployment token retrieved"
}

# Set GitHub secrets
set_github_secrets() {
    log_step "Setting GitHub Repository Secrets"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would set the following GitHub secrets:"
        echo "  - AZURE_CREDENTIALS"
        echo "  - AZURE_FUNCTIONAPP_PUBLISH_PROFILE"
        echo "  - AZURE_FUNCTIONAPP_NAME"
        [[ -n "$SWA_TOKEN" ]] && echo "  - AZURE_STATIC_WEB_APPS_API_TOKEN"
        return 0
    fi

    # Ensure we have the repository context and that the authenticated user has access
    if [[ -z "${REPO:-}" ]]; then
        REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
    fi
    if [[ -z "$REPO" ]]; then
        log_error "Unable to determine GitHub repository or insufficient permissions to view it."
        log_info "Run: gh auth login and grant 'repo' scopes, or run this script from within a cloned repository you own."
        exit 1
    fi
    log_info "Using GitHub repository: $REPO"
    
    # Set AZURE_CREDENTIALS
    log_info "Setting AZURE_CREDENTIALS..."
    if ! echo "$SP_CREDENTIALS" | gh secret set AZURE_CREDENTIALS --repo "$REPO"; then
        log_error "Failed to set AZURE_CREDENTIALS. This commonly means the authenticated GitHub user or token lacks permissions to manage secrets for '$REPO'."
        log_info "Ensure you ran: gh auth login (with 'repo' scopes) or use a token with 'repo' and 'admin:repo_hook' permissions."
        exit 1
    fi
    log_success "AZURE_CREDENTIALS set"
    
    # Set AZURE_FUNCTIONAPP_PUBLISH_PROFILE
    log_info "Setting AZURE_FUNCTIONAPP_PUBLISH_PROFILE..."
    if ! echo "$FUNCTION_PUBLISH_PROFILE" | gh secret set AZURE_FUNCTIONAPP_PUBLISH_PROFILE --repo "$REPO"; then
        log_error "Failed to set AZURE_FUNCTIONAPP_PUBLISH_PROFILE for '$REPO'"
        exit 1
    fi
    log_success "AZURE_FUNCTIONAPP_PUBLISH_PROFILE set"
    
    # Set AZURE_FUNCTIONAPP_NAME
    log_info "Setting AZURE_FUNCTIONAPP_NAME..."
    if ! echo "$FUNCTION_APP_NAME" | gh secret set AZURE_FUNCTIONAPP_NAME --repo "$REPO"; then
        log_error "Failed to set AZURE_FUNCTIONAPP_NAME for '$REPO'"
        exit 1
    fi
    log_success "AZURE_FUNCTIONAPP_NAME set"
    
    # Set SWA token if available
    if [[ -n "$SWA_TOKEN" ]]; then
        log_info "Setting AZURE_STATIC_WEB_APPS_API_TOKEN..."
        if ! echo "$SWA_TOKEN" | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN --repo "$REPO"; then
            log_error "Failed to set AZURE_STATIC_WEB_APPS_API_TOKEN for '$REPO'"
            exit 1
        fi
        log_success "AZURE_STATIC_WEB_APPS_API_TOKEN set"
    fi
}

# Verify setup
verify_setup() {
    log_step "Verifying Configuration"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would verify all secrets are set"
        return 0
    fi
    
    log_info "Checking GitHub secrets..."
    local secrets=$(gh secret list)
    
    local all_good=true
    
    for secret in "AZURE_CREDENTIALS" "AZURE_FUNCTIONAPP_PUBLISH_PROFILE" "AZURE_FUNCTIONAPP_NAME"; do
        if echo "$secrets" | grep -q "^$secret"; then
            log_success "✓ $secret is set"
        else
            log_error "✗ $secret is NOT set"
            all_good=false
        fi
    done
    
    if [[ -n "$SWA_NAME" ]]; then
        if echo "$secrets" | grep -q "^AZURE_STATIC_WEB_APPS_API_TOKEN"; then
            log_success "✓ AZURE_STATIC_WEB_APPS_API_TOKEN is set"
        else
            log_warning "⚠ AZURE_STATIC_WEB_APPS_API_TOKEN is NOT set"
        fi
    fi
    
    if [[ "$all_good" == "true" ]]; then
        log_success "All required secrets are configured!"
    else
        log_error "Some secrets are missing"
        return 1
    fi
}

# Main execution
main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --resource-group)
                RESOURCE_GROUP="$2"
                shift 2
                ;;
            --non-interactive)
                NON_INTERACTIVE=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done
    
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  WireGuard SPA - Automated Setup${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "Running in DRY RUN mode - no changes will be made"
        echo ""
    fi
    
    # Run setup steps
    check_prerequisites
    discover_resources
    setup_service_principal
    setup_managed_identity
    get_function_publish_profile
    get_swa_token
    set_github_secrets
    verify_setup
    
    # Success message
    echo ""
    log_step "Setup Complete!"
    echo ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "This was a dry run. Run without --dry-run to apply changes."
    else
        log_success "All secrets and permissions have been configured!"
        echo ""
        log_info "Next steps:"
        echo "  1. Run validation workflow: gh workflow run validate-secrets.yml"
        echo "  2. Provision infrastructure: gh workflow run infra-provision-and-deploy.yml"
        echo "  3. Deploy application: gh workflow run deploy-backend.yml && gh workflow run deploy-frontend.yml"
        echo ""
        log_info "For more information, see: SETUP-CREDENTIALS.md"
    fi
}

# Run main function
main "$@"
