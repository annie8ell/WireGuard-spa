"""
Authentication and authorization utilities for Azure Static Web Apps.
Uses SWA's built-in role-based authentication.
"""
import base64
import json
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def validate_user(req) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates the user by decoding the X-MS-CLIENT-PRINCIPAL header
    and checking for the 'invited' role as defense in depth.
    
    SWA authentication should already enforce invited users only,
    but this provides an additional security layer.
    
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
        
        # Check for 'invited' role as defense in depth
        # SWA's configuration should already restrict access to invited users,
        # but we verify the role here for additional security
        user_roles = principal_data.get('userRoles', [])
        
        if 'invited' not in user_roles:
            logger.warning(f'User {user_email} does not have invited role. Roles: {user_roles}')
            return False, user_email, f'User {user_email} is not an invited user'
        
        logger.info(f'User {user_email} validated successfully with invited role')
        return True, user_email, None
        
    except Exception as e:
        logger.error(f'Error validating user: {str(e)}')
        return False, None, f'Authentication error: {str(e)}'
