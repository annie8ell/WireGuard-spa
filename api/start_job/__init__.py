"""
Start Job Function - POST /api/start_job

Returns 202 Accepted with operationId and Location header pointing to job_status endpoint.
Initiates async VM and WireGuard tunnel provisioning.
This is a pass-through endpoint - it starts the VM creation and returns immediately.
"""
import logging
import json
import azure.functions as func

# Import shared modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.auth import validate_user
from shared.vm_provisioner import get_vm_provisioner

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to start a new VM provisioning job.
    
    Returns 202 Accepted with:
    - operationId in response body (the VM name)
    - Location header pointing to /api/job_status?id={operationId}
    
    This is a pass-through endpoint - it starts the VM creation and returns immediately.
    """
    # Handle CORS preflight
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-MS-CLIENT-PRINCIPAL"
            }
        )
    
    try:
        # Validate user authentication and check for 'invited' role
        is_valid, user_email, error_msg = validate_user(req)
        
        if not is_valid:
            logger.warning(f"Unauthorized access attempt: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=403,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}
        
        # Generate VM name (this is the operation ID)
        import time
        vm_name = f"wg-{int(time.time())}"
        location = req_body.get('location', 'eastus')
        
        logger.info(f"Starting VM creation for {vm_name} (user: {user_email})")
        
        # Start VM creation asynchronously
        provisioner = get_vm_provisioner()
        success, error_msg, operation_data = provisioner.create_vm(vm_name, location)
        
        if not success:
            logger.error(f"Failed to start VM creation: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=500,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        # Get operation ID (VM name)
        operation_id = operation_data.get('operationId', vm_name)
        
        # Build status URL
        status_url = f"/api/job_status?id={operation_id}"
        
        logger.info(f"VM creation started for {operation_id}, returning 202")
        
        # Return 202 Accepted
        return func.HttpResponse(
            json.dumps({
                "operationId": operation_id,
                "status": "accepted",
                "statusQueryUrl": status_url
            }),
            status_code=202,
            mimetype="application/json",
            headers={
                "Location": status_url,
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "Location"
            }
        )
        
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "details": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
