"""
Status proxy function - Provides a normalized view of orchestration status.

This endpoint simplifies status checking for the SPA by:
- Reducing Durable Functions-specific fields
- Providing a cleaner JSON response
- Adding CORS headers for browser access
"""
import logging
import json
import azure.functions as func
import azure.durable_functions as df

logger = logging.getLogger(__name__)


async def main(req: func.HttpRequest, client: str) -> func.HttpResponse:
    """
    Returns the status of a durable orchestration instance.
    
    Route: /api/status_proxy/{instanceId}
    """
    try:
        instance_id = req.route_params.get('instanceId')
        
        if not instance_id:
            return func.HttpResponse(
                json.dumps({'error': 'Instance ID is required'}),
                status_code=400,
                mimetype='application/json'
            )
        
        # Get the orchestration client
        durable_client = df.DurableOrchestrationClient(client)
        
        # Get the status
        status = await durable_client.get_status(instance_id)
        
        if not status:
            return func.HttpResponse(
                json.dumps({'error': 'Instance not found'}),
                status_code=404,
                mimetype='application/json'
            )
        
        # Normalize the response for the SPA
        normalized_status = {
            'instanceId': status.instance_id,
            'runtimeStatus': status.runtime_status.name if status.runtime_status else 'Unknown',
            'input': status.input,
            'output': status.output,
            'createdTime': status.created_time.isoformat() if status.created_time else None,
            'lastUpdatedTime': status.last_updated_time.isoformat() if status.last_updated_time else None,
            'customStatus': status.custom_status
        }
        
        response = func.HttpResponse(
            json.dumps(normalized_status),
            status_code=200,
            mimetype='application/json'
        )
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response
        
    except Exception as e:
        logger.error(f'Error in status_proxy: {str(e)}', exc_info=True)
        return func.HttpResponse(
            json.dumps({'error': 'Internal server error', 'details': str(e)}),
            status_code=500,
            mimetype='application/json'
        )
