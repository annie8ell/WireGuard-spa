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
from shared.upstream import get_upstream_provider

logger = logging.getLogger(__name__)


def _process_job_async(operation_id: str, user_email: str, request_data: dict):
    """
    Process the job asynchronously.
    This runs in a background thread and updates the status store.
    """
    store = get_status_store()
    provider = get_upstream_provider()
    
    try:
        # Update status to running
        store.set_running(operation_id, "Contacting upstream provider...")
        logger.info(f"Starting upstream provisioning for job {operation_id}")
        
        # Call upstream provider to start provisioning
        success, error_msg, upstream_data = provider.start_provisioning(user_email, request_data)
        
        if not success:
            logger.error(f"Upstream provisioning failed for job {operation_id}: {error_msg}")
            store.set_failed(operation_id, error_msg or "Unknown error from upstream")
            return
        
        # Store upstream reference
        store.update_job(
            operation_id,
            upstreamId=upstream_data.get("upstream_id"),
            progress="Provisioning VM and WireGuard tunnel..."
        )
        
        # Poll upstream for completion
        # In production, this could be optimized with webhooks or separate worker process
        upstream_id = upstream_data.get("upstream_id")
        if upstream_id:
            _poll_upstream_status(operation_id, upstream_id, store, provider)
        else:
            # If no upstream ID, mark as completed with the data we have
            store.set_completed(operation_id, upstream_data)
            
    except Exception as e:
        logger.error(f"Error processing job {operation_id}: {str(e)}", exc_info=True)
        store.set_failed(operation_id, f"Internal error: {str(e)}")


def _poll_upstream_status(operation_id: str, upstream_id: str, store, provider, max_attempts: int = 60):
    """
    Poll upstream provider for status updates.
    Simple implementation - in production, consider separate worker or webhook.
    """
    import time
    
    for attempt in range(max_attempts):
        time.sleep(5)  # Poll every 5 seconds
        
        success, error_msg, status_data = provider.get_status(upstream_id)
        
        if not success:
            logger.error(f"Failed to get status for {upstream_id}: {error_msg}")
            store.set_failed(operation_id, error_msg or "Lost contact with upstream")
            return
        
        upstream_status = status_data.get("status", "").lower()
        progress = status_data.get("progress", "Processing...")
        
        if upstream_status == "completed":
            result = status_data.get("result", {})
            store.set_completed(operation_id, result)
            logger.info(f"Job {operation_id} completed successfully")
            return
        elif upstream_status == "failed":
            error = status_data.get("error", "Upstream job failed")
            store.set_failed(operation_id, error)
            logger.error(f"Job {operation_id} failed: {error}")
            return
        else:
            # Still running, update progress
            store.update_job(operation_id, progress=progress)
    
    # Timeout reached
    store.set_failed(operation_id, "Job timed out after 5 minutes")
    logger.warning(f"Job {operation_id} timed out")


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
