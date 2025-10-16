"""
Authentication and authorization utilities for Azure Static Web Apps.
"""
import base64
import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_allowed_emails() -> list:
    """
    Get the list of allowed email addresses from environment variable.
    Falls back to seed list if not configured.
    """
    allowed_emails_str = os.environ.get('ALLOWED_EMAILS', 'annie8ell@gmail.com')
    return [email.strip() for email in allowed_emails_str.split(',')]


def validate_user(req) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validates the user by decoding the X-MS-CLIENT-PRINCIPAL header
    and checking against the allowlist.
    
    Returns:
        tuple: (is_valid, email, error_message)
    """
    try:
        # Get the X-MS-CLIENT-PRINCIPAL header
        principal_header = req.headers.get('X-MS-CLIENT-PRINCIPAL')
        
        if not principal_header:
            logger.warning('No X-MS-CLIENT-PRINCIPAL header found')
            return False, None, 'Authentication required'
        
        # Decode the base64 JSON payload
        principal_json = base64.b64decode(principal_header).decode('utf-8')
        principal_data = json.loads(principal_json)
        
        # Extract user email
        user_email = principal_data.get('userDetails')
        
        if not user_email:
            logger.warning('No userDetails in principal data')
            return False, None, 'User email not found'
        
        # Check allowlist
        allowed_emails = get_allowed_emails()
        
        if user_email not in allowed_emails:
            logger.warning(f'User {user_email} not in allowlist')
            return False, user_email, f'User {user_email} is not authorized'
        
        logger.info(f'User {user_email} validated successfully')
        return True, user_email, None
        
    except Exception as e:
        logger.error(f'Error validating user: {str(e)}')
        return False, None, f'Authentication error: {str(e)}'
