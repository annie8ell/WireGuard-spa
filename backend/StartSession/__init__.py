"""HTTP-triggered function to start a new WireGuard session."""
import logging
import json
import azure.functions as func
import azure.durable_functions as df
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.auth import validate_user

async def main(req: func.HttpRequest, starter: str) -> func.HttpResponse:
    """Start a new WireGuard session orchestration."""
    logging.info('StartSession function triggered')
    
    # Validate user
    is_valid, user_email, error_msg = validate_user(req)
    if not is_valid:
        return func.HttpResponse(
            json.dumps({'error': error_msg}),
            status_code=401,
            mimetype='application/json'
        )
    
    # Get duration from request (default 1 hour)
    duration = 3600
    try:
        req_body = req.get_json()
        duration = req_body.get('duration', 3600)
    except:
        pass
    
    # Start orchestration
    client = df.DurableOrchestrationClient(starter)
    instance_id = await client.start_new(
        'WireGuardOrchestrator',
        None,
        {
            'user_email': user_email,
            'duration': duration
        }
    )
    
    logging.info(f"Started orchestration {instance_id} for user {user_email}")
    
    # Get status URL
    response = client.create_check_status_response(req, instance_id)
    
    return func.HttpResponse(
        json.dumps({
            'instanceId': instance_id,
            'user_email': user_email,
            'duration': duration,
            'statusQueryGetUri': response.get_body().decode()
        }),
        status_code=202,
        mimetype='application/json'
    )
