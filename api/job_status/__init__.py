"""
Job Status Function - GET /api/job_status?id={operationId}

Returns current job status, progress, and result (when completed) or error (when failed).
"""
import logging
import json
import azure.functions as func

# Import shared modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.status_store import get_status_store

logger = logging.getLogger(__name__)


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to check job status.
    
    Query parameters:
    - id: operationId returned from start_job
    
    Returns:
    - 200 OK with job status (pending/running/completed/failed)
    - 404 Not Found if operationId is invalid
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
        # Get operation ID from query parameters
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
        
        # Get job from status store
        store = get_status_store()
        job = store.get_job(operation_id)
        
        if not job:
            return func.HttpResponse(
                json.dumps({"error": "Job not found", "operationId": operation_id}),
                status_code=404,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
        # Build response
        response_data = {
            "operationId": job["operationId"],
            "status": job["status"],
            "progress": job.get("progress"),
            "createdAt": job["createdAt"],
            "lastUpdatedAt": job["lastUpdatedAt"]
        }
        
        # Include result if completed
        if job["status"] == "completed" and job.get("result"):
            response_data["result"] = job["result"]
        
        # Include error if failed
        if job["status"] == "failed" and job.get("error"):
            response_data["error"] = job["error"]
        
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
