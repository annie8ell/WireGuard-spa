"""HTTP-triggered function to get WireGuard session status."""
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
    """Get status of a WireGuard session."""
    logging.info('GetStatus function triggered')
    
    # Validate user
    is_valid, user_email, error_msg = validate_user(req)
    if not is_valid:
        return func.HttpResponse(
            json.dumps({'error': error_msg}),
            status_code=401,
            mimetype='application/json'
        )
    
    # Get instance ID from query or body
    instance_id = req.params.get('instanceId')
    if not instance_id:
        try:
            req_body = req.get_json()
            instance_id = req_body.get('instanceId')
        except:
            pass
    
    if not instance_id:
        return func.HttpResponse(
            json.dumps({'error': 'instanceId required'}),
            status_code=400,
            mimetype='application/json'
        )
    
    # Get orchestration status
    client = df.DurableOrchestrationClient(starter)
    status = await client.get_status(instance_id)
    
    if status:
        return func.HttpResponse(
            json.dumps({
                'instanceId': status.instance_id,
                'runtimeStatus': status.runtime_status.name,
                'input': status.input_,
                'output': status.output,
                'createdTime': status.created_time.isoformat() if status.created_time else None,
                'lastUpdatedTime': status.last_updated_time.isoformat() if status.last_updated_time else None
            }),
            status_code=200,
            mimetype='application/json'
        )
    else:
        return func.HttpResponse(
            json.dumps({'error': 'Instance not found'}),
            status_code=404,
            mimetype='application/json'
        )
