"""Authentication utilities for WireGuard backend."""
import json
from .config import get_allowed_emails

def validate_user(req):
    """
    Validate user authentication from Azure Static Web Apps.
    Returns tuple (is_valid, user_email, error_message).
    """
    # Check for the StaticWebApps authentication header
    client_principal_header = req.headers.get('x-ms-client-principal')
    
    if not client_principal_header:
        return False, None, "No authentication header found"
    
    try:
        # Decode the base64 encoded JSON
        import base64
        decoded = base64.b64decode(client_principal_header)
        principal = json.loads(decoded)
        
        user_email = principal.get('userDetails', '').lower()
        
        if not user_email:
            return False, None, "No email found in authentication"
        
        allowed_emails = [email.lower() for email in get_allowed_emails()]
        
        if user_email not in allowed_emails:
            return False, user_email, f"User {user_email} is not authorized"
        
        return True, user_email, None
        
    except Exception as e:
        return False, None, f"Authentication error: {str(e)}"
