"""Configuration management for WireGuard backend."""
import os

# Default allowed users
DEFAULT_ALLOWED_EMAILS = "awwsawws@gmail.com,awwsawws@hotmail.com"

def get_allowed_emails():
    """Get list of allowed email addresses."""
    emails_str = os.environ.get('ALLOWED_EMAILS', DEFAULT_ALLOWED_EMAILS)
    return [email.strip() for email in emails_str.split(',')]

def is_dry_run():
    """Check if dry run mode is enabled."""
    return os.environ.get('DRY_RUN', 'false').lower() == 'true'

def get_backend_mode():
    """Get backend mode (vm or aci)."""
    return os.environ.get('BACKEND_MODE', 'vm').lower()

def get_azure_subscription_id():
    """Get Azure subscription ID."""
    return os.environ.get('AZURE_SUBSCRIPTION_ID', '')

def get_azure_resource_group():
    """Get Azure resource group name."""
    return os.environ.get('AZURE_RESOURCE_GROUP', '')
