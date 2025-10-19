#!/bin/bash

##############################################################################
# Script: get-swa-deploy-token.sh
# Description: Retrieves the Azure Static Web App deployment token using Azure CLI
# Usage: ./get-swa-deploy-token.sh <STATIC_WEB_APP_NAME> <RESOURCE_GROUP>
##############################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to display usage information
usage() {
    cat << EOF
Usage: $0 <STATIC_WEB_APP_NAME> <RESOURCE_GROUP>

Retrieves the deployment token (API key) for an Azure Static Web App.

Arguments:
  STATIC_WEB_APP_NAME  Name of the Azure Static Web App
  RESOURCE_GROUP       Azure Resource Group containing the Static Web App

Examples:
  # Display deployment token to stdout
  $0 my-static-web-app my-resource-group

  # Set as GitHub secret (requires gh CLI)
  $0 my-static-web-app my-resource-group | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN

  # Save to file (not recommended for security)
  OUTPUT_FILE=swa-token.txt $0 my-static-web-app my-resource-group

Environment Variables:
  AZURE_SUBSCRIPTION_ID   (Optional) Azure subscription ID to use
  OUTPUT_FILE             (Optional) Write output to file instead of stdout

Prerequisites:
  - Azure CLI must be installed and authenticated (az login)
  - User must have read permissions on the Static Web App

Security Note:
  This token provides deployment access to your Static Web App.
  - Do NOT commit this token to source control
  - Do NOT share this token publicly
  - Store it securely in GitHub Secrets or Azure Key Vault
  - Rotate it regularly via Azure Portal

EOF
    exit 1
}

# Function to check if Azure CLI is installed and authenticated
check_prerequisites() {
    # Check if az CLI is installed
    if ! command -v az &> /dev/null; then
        echo -e "${RED}Error: Azure CLI is not installed.${NC}" >&2
        echo "Please install it from: https://docs.microsoft.com/cli/azure/install-azure-cli" >&2
        exit 1
    fi

    # Check if logged in to Azure
    if ! az account show &> /dev/null; then
        echo -e "${RED}Error: Not logged in to Azure CLI.${NC}" >&2
        echo "Please run 'az login' first." >&2
        exit 1
    fi
}

# Function to validate Static Web App exists
validate_static_web_app() {
    local swa_name="$1"
    local resource_group="$2"

    echo -e "${YELLOW}Validating Static Web App '${swa_name}' in resource group '${resource_group}'...${NC}" >&2

    if ! az staticwebapp show \
        --name "$swa_name" \
        --resource-group "$resource_group" \
        --output none 2>/dev/null; then
        echo -e "${RED}Error: Static Web App '${swa_name}' not found in resource group '${resource_group}'.${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}Static Web App found.${NC}" >&2
}

# Function to retrieve deployment token
get_deployment_token() {
    local swa_name="$1"
    local resource_group="$2"

    echo -e "${YELLOW}Retrieving deployment token...${NC}" >&2

    # Get the API key (deployment token)
    local token
    if ! token=$(az staticwebapp secrets list \
        --name "$swa_name" \
        --resource-group "$resource_group" \
        --query 'properties.apiKey' -o tsv 2>&1); then
        echo -e "${RED}Error: Failed to retrieve deployment token.${NC}" >&2
        echo "$token" >&2
        exit 1
    fi

    # Validate token is not empty
    if [[ -z "$token" || "$token" == "null" ]]; then
        echo -e "${RED}Error: Deployment token is empty or null.${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}Successfully retrieved deployment token.${NC}" >&2
    
    # Display first and last 4 characters for verification (don't show full token in logs)
    local token_preview="${token:0:4}...${token: -4}"
    echo -e "${GREEN}Token preview: ${token_preview}${NC}" >&2
    
    echo "$token"
}

# Main script logic
main() {
    # Check for help flag
    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        usage
    fi

    # Check required arguments
    if [[ $# -lt 2 ]]; then
        echo -e "${RED}Error: Missing required arguments.${NC}" >&2
        echo "" >&2
        usage
    fi

    local swa_name="$1"
    local resource_group="$2"

    # Check prerequisites
    check_prerequisites

    # Set subscription if provided
    if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
        echo -e "${YELLOW}Setting Azure subscription to: ${AZURE_SUBSCRIPTION_ID}${NC}" >&2
        az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    fi

    # Validate Static Web App exists
    validate_static_web_app "$swa_name" "$resource_group"

    # Get deployment token
    local token
    token=$(get_deployment_token "$swa_name" "$resource_group")

    # Output to file or stdout
    if [[ -n "${OUTPUT_FILE:-}" ]]; then
        echo "$token" > "$OUTPUT_FILE"
        echo -e "${GREEN}Deployment token written to: ${OUTPUT_FILE}${NC}" >&2
        echo -e "${YELLOW}WARNING: Token file contains sensitive data. Do not commit to source control!${NC}" >&2
    else
        echo "$token"
    fi

    # Display usage instructions
    echo "" >&2
    echo -e "${GREEN}=== Next Steps ===${NC}" >&2
    echo "To set this as a GitHub secret, run:" >&2
    echo "" >&2
    echo "  # Using gh CLI (recommended):" >&2
    echo "  $0 $swa_name $resource_group | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN" >&2
    echo "" >&2
    echo "  # Or via GitHub Web UI:" >&2
    echo "  1. Copy the token above" >&2
    echo "  2. Navigate to: Settings → Secrets and variables → Actions" >&2
    echo "  3. Create secret: AZURE_STATIC_WEB_APPS_API_TOKEN" >&2
    echo "  4. Paste the token value" >&2
    echo "" >&2
    echo -e "${YELLOW}Security reminder: Keep this token secure and rotate it regularly!${NC}" >&2
}

# Run main function
main "$@"
