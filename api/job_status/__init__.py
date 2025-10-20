"""
Job Status Function - GET /api/job_status?id={operationId}

Returns current job status by querying Azure directly (pass-through).
No local state storage - queries Azure for VM provisioning status.
"""
import logging
import json
import azure.functions as func

# Import shared modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.vm_provisioner import get_vm_provisioner

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to check job status.
    
    Query parameters:
    - id: operationId (VM name) returned from start_job
    
    Returns:
    - 200 OK with job status from Azure
    - 404 Not Found if operationId is invalid
    
    This is a pass-through endpoint - it queries Azure directly for VM status.
    """
    # Handle CORS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-MS-CLIENT-PRINCIPAL"
            }
        )
    
    try:
        # Get operation ID (VM name) from query parameters
        operation_id = req.params.get('id')
        
        if not operation_id:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'id' query parameter"}),
                status_code=400,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        logger.info(f"Checking status for operation {operation_id}")
        
        # Query Azure for VM status (pass-through)
        provisioner = get_vm_provisioner()
        success, error_msg, status_data = provisioner.get_vm_status(operation_id)
        
        if not success:
            logger.error(f"Failed to get VM status: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=500,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        # Build response from Azure data
        response_data = {
            "operationId": operation_id,
            "status": status_data.get('status', 'Unknown')
        }
        
        # Add progress if available
        if 'progress' in status_data:
            response_data['progress'] = status_data['progress']
        
        # Add result if completed
        if status_data.get('status') == 'Succeeded':
            response_data['result'] = {
                'vmName': status_data.get('vmName'),
                'publicIp': status_data.get('publicIp'),
                'confText': status_data.get('confText')
            }
        
        # Add error if failed
        if status_data.get('status') == 'Failed' and 'error' in status_data:
            response_data['error'] = status_data['error']
        
        # Return status
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in job_status: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "details": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
