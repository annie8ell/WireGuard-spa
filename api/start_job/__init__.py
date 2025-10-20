"""
Start Job Function - POST /api/start_job

Returns 202 Accepted with operationId and Location header pointing to job_status endpoint.
Idempotent operation: Returns existing running VM or creates a new one.
Only one WireGuard VM exists at a time per resource group.
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
    HTTP endpoint to get existing WireGuard VM or create a new one (idempotent).
    
    Returns 202 Accepted with:
    - operationId in response body (the VM name)
    - Location header pointing to /api/job_status?id={operationId}
    - isExisting flag (true if returning existing VM, false if creating new)
    - confText and publicIp (if VM is already ready)
    
    Only one WireGuard VM exists at a time. Multiple calls return the same VM.
    """
    try:
        # Validate user authentication and check for 'invited' role
        is_valid, user_email, error_msg = validate_user(req)
        
        if not is_valid:
            logger.warning(f"Unauthorized access attempt: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=403,
                mimetype="application/json"
            )
        
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}
        
        location = req_body.get('location', 'eastus')
        
        logger.info(f"Getting or creating WireGuard VM (user: {user_email})")
        
        # Get existing VM or create new one (idempotent)
        provisioner = get_vm_provisioner()
        success, error_msg, operation_data = provisioner.get_or_create_vm(location)
        
        if not success:
            logger.error(f"Failed to start VM creation: {error_msg}")
            return func.HttpResponse(
                json.dumps({"error": error_msg}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Get operation ID (VM name)
        operation_id = operation_data.get('operationId')
        is_existing = operation_data.get('isExisting', False)
        vm_status = operation_data.get('status', 'accepted')
        
        # Build status URL
        status_url = f"/api/job_status?id={operation_id}"
        
        if is_existing:
            logger.info(f"Returning existing VM {operation_id}, returning 202")
        else:
            logger.info(f"VM creation started for {operation_id}, returning 202")
        
        # Build response data
        response_data = {
            "operationId": operation_id,
            "status": "accepted",
            "statusQueryUrl": status_url,
            "isExisting": is_existing
        }
        
        # If VM is already succeeded and has config, include it
        if vm_status == 'Succeeded' and operation_data.get('confText'):
            response_data["confText"] = operation_data["confText"]
            response_data["publicIp"] = operation_data.get("publicIp")
        
        # Return 202 Accepted
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=202,
            mimetype="application/json",
            headers={
                "Location": status_url
            }
        )
        
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
