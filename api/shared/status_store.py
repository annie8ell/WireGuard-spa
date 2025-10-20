"""
Status store for tracking job progress.
Starts as in-memory implementation, can be swapped for Redis/Table Storage.
"""
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StatusStore:
    """In-memory status store for job tracking."""
    
    def __init__(self):
        self._store: Dict[str, dict] = {}
        self._lock = threading.Lock()
        
    def create_job(self, operation_id: str, user_email: str, request_data: dict) -> dict:
        """Create a new job entry."""
        with self._lock:
            job_data = {
                "operationId": operation_id,
                "status": JobStatus.PENDING,
                "userEmail": user_email,
                "requestData": request_data,
                "createdAt": datetime.utcnow().isoformat(),
                "lastUpdatedAt": datetime.utcnow().isoformat(),
                "progress": "Job created",
                "result": None,
                "error": None
            }
            self._store[operation_id] = job_data
            return job_data
    
    def get_job(self, operation_id: str) -> Optional[dict]:
        """Get job status by operation ID."""
        with self._lock:
            return self._store.get(operation_id)
    
    def update_job(self, operation_id: str, **updates) -> Optional[dict]:
        """Update job status."""
        with self._lock:
            if operation_id not in self._store:
                return None
            
            job = self._store[operation_id]
            job.update(updates)
            job["lastUpdatedAt"] = datetime.utcnow().isoformat()
            return job
    
    def set_running(self, operation_id: str, progress: str = "Processing..."):
        """Mark job as running."""
        return self.update_job(
            operation_id,
            status=JobStatus.RUNNING,
            progress=progress
        )
    
    def set_completed(self, operation_id: str, result: dict):
        """Mark job as completed."""
        return self.update_job(
            operation_id,
            status=JobStatus.COMPLETED,
            progress="Completed successfully",
            result=result
        )
    
    def set_failed(self, operation_id: str, error: str):
        """Mark job as failed."""
        return self.update_job(
            operation_id,
            status=JobStatus.FAILED,
            progress="Failed",
            error=error
        )
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than specified hours."""
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
            to_remove = []
            
            for op_id, job in self._store.items():
                created = datetime.fromisoformat(job["createdAt"])
                if created < cutoff:
                    to_remove.append(op_id)
            
            for op_id in to_remove:
                del self._store[op_id]
            
            return len(to_remove)


# Singleton instance
_store_instance = None
_store_lock = threading.Lock()


def get_status_store() -> StatusStore:
    """Get the singleton status store instance."""
    global _store_instance
    
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = StatusStore()
    
    return _store_instance
