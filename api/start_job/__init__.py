"""
Start Job Function - POST /api/start_job

Returns 202 Accepted with operationId and Location header pointing to job_status endpoint.
Initiates async VM and WireGuard tunnel provisioning via upstream provider.
"""
import logging
import json
import uuid
import threading
import azure.functions as func

# Import shared modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.auth import validate_user
from shared.status_store import get_status_store
from shared.vm_provisioner import get_vm_provisioner

logger = logging.getLogger(__name__)


def _process_job_async(operation_id: str, user_email: str, request_data: dict):
    """
    Process the job asynchronously.
    This runs in a background thread and updates the status store.
    """
    store = get_status_store()
    provisioner = get_vm_provisioner()
    
    try:
        # Update status to running
        store.set_running(operation_id, "Creating Azure VM with WireGuard...")
        logger.info(f"Starting VM provisioning for job {operation_id}")
        
        # Generate VM name
        import time
        vm_name = f"wg-{int(time.time())}"
        location = request_data.get('location', 'eastus')
        
        # Create VM
        success, error_msg, vm_data = provisioner.create_vm(vm_name, location)
        
        if not success:
            logger.error(f"VM provisioning failed for job {operation_id}: {error_msg}")
            store.set_failed(operation_id, error_msg or "Unknown error during VM creation")
            return
        
        # Mark as completed with VM data
        logger.info(f"VM {vm_name} created successfully for job {operation_id}")
        store.set_completed(operation_id, vm_data)
        
        # TODO: Schedule auto-delete after 30 minutes
        # This could be done via:
        # 1. Azure Function timer trigger that checks for expired VMs
        # 2. Azure Automation runbook
        # 3. Storing expiry time and having a cleanup function
        logger.info(f"VM {vm_name} scheduled for auto-deletion after 30 minutes (TODO)")
            
    except Exception as e:
        logger.error(f"Error processing job {operation_id}: {str(e)}", exc_info=True)
        store.set_failed(operation_id, f"Internal error: {str(e)}")



def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to start a new provisioning job.
    
    Returns 202 Accepted with:
    - operationId in response body
    - Location header pointing to /api/job_status?id={operationId}
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
        # Validate user authentication
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
        
        # Generate operation ID
        operation_id = str(uuid.uuid4())
        
        # Create job in status store
        store = get_status_store()
        store.create_job(operation_id, user_email, req_body)
        
        logger.info(f"Created job {operation_id} for user {user_email}")
        
        # Start async processing in background thread
        thread = threading.Thread(
            target=_process_job_async,
            args=(operation_id, user_email, req_body),
            daemon=True
        )
        thread.start()
        
        # Build status URL
        # Note: In SWA, the host might be different, adjust as needed
        status_url = f"/api/job_status?id={operation_id}"
        
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
