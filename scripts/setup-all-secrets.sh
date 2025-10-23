#!/bin/bash

##############################################################################
# Script: setup-all-secrets.sh
# Description: Automated setup of Azure permissions and GitHub secrets for SWA Functions
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
TEARDOWN=false
SP_NAME="wireguard-spa-vm-provisioner"

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Automated setup of Azure permissions and GitHub repository secrets for WireGuard SPA (SWA Functions).

This script will:
1. Discover Azure resources (or use provided values)
2. Create/verify Service Principal with VM provisioning permissions (scoped to resource group)
3. Retrieve Static Web App deployment token
4. Set GitHub repository secrets automatically

Options:
  --resource-group <name>   Specify Azure resource group name
  --non-interactive         Run without prompts (use defaults/discovered values)
  --force                   Override existing secrets
  --dry-run                 Show what would be done without making changes
  --teardown                Remove Service Principal and GitHub secrets
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
    
    # Skip Azure and GitHub login checks in dry-run mode
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Skipping Azure and GitHub authentication checks"
        return 0
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
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would discover Azure resources"
        SUBSCRIPTION_ID="dummy-subscription-id"
        RESOURCE_GROUP="${RESOURCE_GROUP:-dummy-resource-group}"
        SWA_NAME="dummy-swa-name"
        log_info "Using dummy values for dry run"
        return 0
    fi
    
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
    
    # Find Static Web App
    SWA_NAME=$(az staticwebapp list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)
    if [[ -z "$SWA_NAME" || "$SWA_NAME" == "null" ]]; then
        log_error "No Static Web App found in resource group: $RESOURCE_GROUP"
        log_info "Available Static Web Apps:"
        az staticwebapp list --query "[].name" -o tsv
        exit 1
    fi
    log_success "Found Static Web App: $SWA_NAME"
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
    
    # Create new Service Principal with scoped permissions
    log_info "Creating Service Principal with VM Contributor role on resource group..."
    
    local sp_output=$(az ad sp create-for-rbac \
        --name "$SP_NAME" \
        --role "Virtual Machine Contributor" \
        --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
        --sdk-auth)
    
    # Store the full sdk-auth JSON for GitHub secret and extract the app id
    SP_CREDENTIALS="$sp_output"
    SP_APP_ID=$(echo "$sp_output" | jq -r '.clientId')
    
    log_success "Service Principal created: $SP_APP_ID"
    
    # Add Network Contributor role as well
    log_info "Assigning Network Contributor role..."
    az role assignment create \
        --assignee "$SP_APP_ID" \
        --role "Network Contributor" \
        --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
        --output none 2>/dev/null || log_warning "Role may already be assigned"
    
    log_success "VM and Network Contributor roles assigned to Service Principal"
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
        echo "  - AZURE_STATIC_WEB_APPS_API_TOKEN"
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
    
    # Set SWA token
    log_info "Setting AZURE_STATIC_WEB_APPS_API_TOKEN..."
    if ! echo "$SWA_TOKEN" | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN --repo "$REPO"; then
        log_error "Failed to set AZURE_STATIC_WEB_APPS_API_TOKEN for '$REPO'"
        exit 1
    fi
    log_success "AZURE_STATIC_WEB_APPS_API_TOKEN set"
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
    
    # Check required secrets
    for secret in "AZURE_CREDENTIALS" "AZURE_STATIC_WEB_APPS_API_TOKEN"; do
        if echo "$secrets" | grep -q "^$secret"; then
            log_success "✓ $secret is set"
        else
            log_error "✗ $secret is NOT set"
            all_good=false
        fi
    done
    
    if [[ "$all_good" == "true" ]]; then
        log_success "All required secrets are configured!"
    else
        log_error "Some secrets are missing"
        return 1
    fi
}

# Function to tear down secrets and resources
teardown() {
    log_step "Tearing Down Secrets and Resources"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would tear down Service Principal and GitHub secrets"
        return 0
    fi
    
    # Confirm teardown
    if [[ "$NON_INTERACTIVE" == "false" ]]; then
        echo -n "This will delete the Service Principal '$SP_NAME' and remove GitHub secrets. Continue? (y/N): "
        read confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            log_info "Teardown cancelled"
            exit 0
        fi
    fi
    
    # Remove GitHub secrets
    log_info "Removing GitHub secrets..."
    gh secret delete AZURE_CREDENTIALS --repo "$REPO" 2>/dev/null || log_warning "AZURE_CREDENTIALS not found or already removed"
    gh secret delete AZURE_STATIC_WEB_APPS_API_TOKEN --repo "$REPO" 2>/dev/null || log_warning "AZURE_STATIC_WEB_APPS_API_TOKEN not found or already removed"
    log_success "GitHub secrets removed"
    
    # Delete Service Principal
    log_info "Deleting Service Principal..."
    SP_APP_ID=$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv 2>/dev/null)
    if [[ -n "$SP_APP_ID" && "$SP_APP_ID" != "null" ]]; then
        az ad sp delete --id "$SP_APP_ID" 2>/dev/null || log_warning "Failed to delete Service Principal"
        log_success "Service Principal deleted"
    else
        log_warning "Service Principal '$SP_NAME' not found"
    fi
    
    log_success "Teardown complete!"
}
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
            --teardown)
                TEARDOWN=true
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
    
    # Handle teardown
    if [[ "$TEARDOWN" == "true" ]]; then
        teardown
        exit 0
    fi
    
    # Run setup steps
    check_prerequisites
    discover_resources
    setup_service_principal
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
        echo "  2. Deploy application: gh workflow run azure-static-web-apps.yml"
        echo ""
        log_info "For more information, see: SETUP-CREDENTIALS.md"
    fi
}

# Run main function
main "$@"
