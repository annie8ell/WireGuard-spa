#!/bin/bash

##############################################################################
# Script: get-function-publish-profile.sh
# Description: Retrieves the Azure Function App publish profile using Azure CLI
# Usage: ./get-function-publish-profile.sh <FUNCTION_APP_NAME> <RESOURCE_GROUP>
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
Usage: $0 <FUNCTION_APP_NAME> <RESOURCE_GROUP>

Retrieves the publish profile (XML) for an Azure Function App.

Arguments:
  FUNCTION_APP_NAME    Name of the Azure Function App
  RESOURCE_GROUP       Azure Resource Group containing the Function App

Examples:
  # Display publish profile to stdout
  $0 my-function-app my-resource-group

  # Save to file
  $0 my-function-app my-resource-group > publish-profile.xml

  # Set as GitHub secret (requires gh CLI)
  $0 my-function-app my-resource-group | gh secret set AZURE_FUNCTIONAPP_PUBLISH_PROFILE

Environment Variables:
  AZURE_SUBSCRIPTION_ID   (Optional) Azure subscription ID to use
  OUTPUT_FILE             (Optional) Write output to file instead of stdout

Prerequisites:
  - Azure CLI must be installed and authenticated (az login)
  - User must have read permissions on the Function App

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

# Function to validate Function App exists
validate_function_app() {
    local function_app_name="$1"
    local resource_group="$2"

    echo -e "${YELLOW}Validating Function App '${function_app_name}' in resource group '${resource_group}'...${NC}" >&2

    if ! az functionapp show \
        --name "$function_app_name" \
        --resource-group "$resource_group" \
        --output none 2>/dev/null; then
        echo -e "${RED}Error: Function App '${function_app_name}' not found in resource group '${resource_group}'.${NC}" >&2
        exit 1
    fi

    echo -e "${GREEN}Function App found.${NC}" >&2
}

# Function to retrieve publish profile
get_publish_profile() {
    local function_app_name="$1"
    local resource_group="$2"

    echo -e "${YELLOW}Retrieving publish profile...${NC}" >&2

    # Get the publish profile
    local publish_profile
    if ! publish_profile=$(az functionapp deployment list-publishing-profiles \
        --name "$function_app_name" \
        --resource-group "$resource_group" \
        --xml 2>&1); then
        echo -e "${RED}Error: Failed to retrieve publish profile.${NC}" >&2
        echo "$publish_profile" >&2
        exit 1
    fi

    echo -e "${GREEN}Successfully retrieved publish profile.${NC}" >&2
    echo "$publish_profile"
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

    local function_app_name="$1"
    local resource_group="$2"

    # Check prerequisites
    check_prerequisites

    # Set subscription if provided
    if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
        echo -e "${YELLOW}Setting Azure subscription to: ${AZURE_SUBSCRIPTION_ID}${NC}" >&2
        az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    fi

    # Validate Function App exists
    validate_function_app "$function_app_name" "$resource_group"

    # Get publish profile
    local publish_profile
    publish_profile=$(get_publish_profile "$function_app_name" "$resource_group")

    # Output to file or stdout
    if [[ -n "${OUTPUT_FILE:-}" ]]; then
        echo "$publish_profile" > "$OUTPUT_FILE"
        echo -e "${GREEN}Publish profile written to: ${OUTPUT_FILE}${NC}" >&2
    else
        echo "$publish_profile"
    fi

    # Display usage instructions
    echo "" >&2
    echo -e "${GREEN}=== Next Steps ===${NC}" >&2
    echo "To set this as a GitHub secret, run one of the following:" >&2
    echo "" >&2
    echo "  # Using gh CLI (recommended):" >&2
    echo "  $0 $function_app_name $resource_group | gh secret set AZURE_FUNCTIONAPP_PUBLISH_PROFILE" >&2
    echo "" >&2
    echo "  # Or save to file and set manually:" >&2
    echo "  OUTPUT_FILE=publish-profile.xml $0 $function_app_name $resource_group" >&2
    echo "  gh secret set AZURE_FUNCTIONAPP_PUBLISH_PROFILE < publish-profile.xml" >&2
    echo "" >&2
}

# Run main function
main "$@"
