"""
HTTP Start function - Initiates the WireGuard VPN provisioning orchestration.
Validates the user against the allowlist before starting the orchestration.
"""
import logging
import json
import azure.functions as func
import azure.durable_functions as df
from shared.auth import validate_user

logger = logging.getLogger(__name__)


async def main(req: func.HttpRequest, starter: str) -> func.HttpResponse:
    """
    HTTP endpoint to start the VPN provisioning orchestration.
    
    This function:
    1. Validates the user by checking X-MS-CLIENT-PRINCIPAL header
    2. Checks if user is in the allowlist
    3. Starts the orchestration if authorized
    """
    try:
        # Validate user
        is_valid, user_email, error_msg = validate_user(req)
        
        if not is_valid:
            logger.warning(f'Unauthorized access attempt: {error_msg}')
            return func.HttpResponse(
                json.dumps({'error': error_msg}),
                status_code=403,
                mimetype='application/json'
            )
        
        # Parse request body (optional, for future extensibility)
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}
        
        # Create orchestration input
        orchestration_input = {
            'user_email': user_email,
            'action': req_body.get('action', 'provision')
        }
        
        # Start the orchestration
        client = df.DurableOrchestrationClient(starter)
        instance_id = await client.start_new(
            orchestration_function_name='orchestrator',
            client_input=orchestration_input
        )
        
        logger.info(f'Started orchestration {instance_id} for user {user_email}')
        
        # Return the orchestration management URLs
        response = client.create_check_status_response(req, instance_id)
        
        # Add CORS headers for SPA
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-MS-CLIENT-PRINCIPAL'
        
        return response
        
    except Exception as e:
        logger.error(f'Error in http_start: {str(e)}', exc_info=True)
        return func.HttpResponse(
            json.dumps({'error': 'Internal server error', 'details': str(e)}),
            status_code=500,
            mimetype='application/json'
        )
