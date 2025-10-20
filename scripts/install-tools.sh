#!/bin/bash

##############################################################################
# Script: install-tools.sh
# Description: Installs Azure CLI and GitHub CLI on various platforms
# Usage: ./install-tools.sh [--help]
##############################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Installs required CLI tools for WireGuard SPA setup:
- Azure CLI (az)
- GitHub CLI (gh)
- Required dependencies (curl, jq, etc.)

Options:
  --help, -h          Show this help message
  --skip-azure        Skip Azure CLI installation
  --skip-github       Skip GitHub CLI installation
  --force             Force reinstall even if tools exist

Examples:
  # Install all tools
  $0

  # Install only Azure CLI
  $0 --skip-github

  # Force reinstall
  $0 --force

EOF
    exit 0
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$ID
            VERSION=$VERSION_ID
        else
            OS="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    
    echo -e "${BLUE}Detected OS: $OS${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Azure CLI
install_azure_cli() {
    echo -e "${YELLOW}Installing Azure CLI...${NC}"
    
    if [[ "$SKIP_AZURE" == "true" ]]; then
        echo -e "${BLUE}Skipping Azure CLI installation${NC}"
        return 0
    fi
    
    if command_exists az && [[ "$FORCE" != "true" ]]; then
        echo -e "${GREEN}Azure CLI is already installed${NC}"
        az version
        return 0
    fi
    
    case "$OS" in
        ubuntu|debian)
            echo -e "${BLUE}Installing Azure CLI on Ubuntu/Debian...${NC}"
            # Get necessary packages
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl apt-transport-https lsb-release gnupg
            
            # Download and install Microsoft signing key
            sudo mkdir -p /etc/apt/keyrings
            curl -sLS https://packages.microsoft.com/keys/microsoft.asc |
                gpg --dearmor |
                sudo tee /etc/apt/keyrings/microsoft.gpg > /dev/null
            sudo chmod go+r /etc/apt/keyrings/microsoft.gpg
            
            # Add Azure CLI repository
            AZ_REPO=$(lsb_release -cs)
            echo "deb [arch=`dpkg --print-architecture` signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" |
                sudo tee /etc/apt/sources.list.d/azure-cli.list
            
            # Install Azure CLI
            sudo apt-get update
            sudo apt-get install -y azure-cli
            ;;
            
        macos)
            echo -e "${BLUE}Installing Azure CLI on macOS...${NC}"
            if command_exists brew; then
                brew update && brew install azure-cli
            else
                echo -e "${RED}Homebrew not found. Please install Homebrew first:${NC}"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                exit 1
            fi
            ;;
            
        *)
            echo -e "${YELLOW}Installing Azure CLI using universal installer...${NC}"
            curl -L https://aka.ms/InstallAzureCLIDeb | bash
            ;;
    esac
    
    # Verify installation
    if command_exists az; then
        echo -e "${GREEN}✓ Azure CLI installed successfully${NC}"
        az version
    else
        echo -e "${RED}✗ Azure CLI installation failed${NC}"
        exit 1
    fi
}

# Install GitHub CLI
install_github_cli() {
    echo -e "${YELLOW}Installing GitHub CLI...${NC}"
    
    if [[ "$SKIP_GITHUB" == "true" ]]; then
        echo -e "${BLUE}Skipping GitHub CLI installation${NC}"
        return 0
    fi
    
    if command_exists gh && [[ "$FORCE" != "true" ]]; then
        echo -e "${GREEN}GitHub CLI is already installed${NC}"
        gh --version
        return 0
    fi
    
    case "$OS" in
        ubuntu|debian)
            echo -e "${BLUE}Installing GitHub CLI on Ubuntu/Debian...${NC}"
            # Add GitHub CLI repository
            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
            sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
            
            # Install GitHub CLI
            sudo apt-get update
            sudo apt-get install -y gh
            ;;
            
        macos)
            echo -e "${BLUE}Installing GitHub CLI on macOS...${NC}"
            if command_exists brew; then
                brew install gh
            else
                echo -e "${RED}Homebrew not found. Please install Homebrew first:${NC}"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                exit 1
            fi
            ;;
            
        *)
            echo -e "${YELLOW}Installing GitHub CLI using universal method...${NC}"
            # Try snap if available
            if command_exists snap; then
                sudo snap install gh
            else
                echo -e "${RED}Unable to install GitHub CLI automatically on this system.${NC}"
                echo "Please install manually: https://github.com/cli/cli#installation"
                exit 1
            fi
            ;;
    esac
    
    # Verify installation
    if command_exists gh; then
        echo -e "${GREEN}✓ GitHub CLI installed successfully${NC}"
        gh --version
    else
        echo -e "${RED}✗ GitHub CLI installation failed${NC}"
        exit 1
    fi
}

# Install additional dependencies
install_dependencies() {
    echo -e "${YELLOW}Installing additional dependencies...${NC}"
    
    local deps_needed=false
    
    if ! command_exists curl; then
        deps_needed=true
    fi
    
    if ! command_exists jq; then
        deps_needed=true
    fi
    
    if [[ "$deps_needed" == "false" ]]; then
        echo -e "${GREEN}All dependencies are already installed${NC}"
        return 0
    fi
    
    case "$OS" in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y curl jq
            ;;
        macos)
            if command_exists brew; then
                brew install curl jq
            fi
            ;;
        *)
            echo -e "${YELLOW}Please ensure curl and jq are installed manually${NC}"
            ;;
    esac
    
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Main installation flow
main() {
    # Parse arguments
    SKIP_AZURE=false
    SKIP_GITHUB=false
    FORCE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                usage
                ;;
            --skip-azure)
                SKIP_AZURE=true
                shift
                ;;
            --skip-github)
                SKIP_GITHUB=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                usage
                ;;
        esac
    done
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  WireGuard SPA - Tool Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # Detect operating system
    detect_os
    echo ""
    
    # Install dependencies
    install_dependencies
    echo ""
    
    # Install Azure CLI
    install_azure_cli
    echo ""
    
    # Install GitHub CLI
    install_github_cli
    echo ""
    
    # Summary
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo ""
    echo "1. Authenticate to Azure:"
    echo -e "   ${YELLOW}az login${NC}"
    echo ""
    echo "2. Authenticate to GitHub:"
    echo -e "   ${YELLOW}gh auth login${NC}"
    echo ""
    echo "3. Run the automated setup:"
    echo -e "   ${YELLOW}./scripts/setup-all-secrets.sh${NC}"
    echo ""
    echo "For more information, see: SETUP-CREDENTIALS.md"
}

# Run main function
main "$@"
