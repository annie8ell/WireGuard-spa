"""
Upstream provider integration for VM and WireGuard tunnel creation.
Configurable via environment variables.
"""
import os
import logging
import requests
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class UpstreamProvider:
    """
    Integration with upstream VM/tunnel provider.
    
    Environment variables:
    - UPSTREAM_BASE_URL: Base URL of the upstream provider API
    - UPSTREAM_API_KEY: API key for authentication
    - DRY_RUN: If "true", simulates responses without calling upstream
    """
    
    def __init__(self):
        self.base_url = os.environ.get("UPSTREAM_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("UPSTREAM_API_KEY", "")
        self.dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
        
        if not self.base_url and not self.dry_run:
            logger.warning("UPSTREAM_BASE_URL not set and DRY_RUN is false")
        
        if not self.api_key and not self.dry_run:
            logger.warning("UPSTREAM_API_KEY not set and DRY_RUN is false")
    
    def _get_headers(self) -> dict:
        """Get HTTP headers for upstream API calls."""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def start_provisioning(self, user_email: str, request_data: dict) -> Tuple[bool, Optional[str], Optional[dict]]:
        """
        Start VM and WireGuard tunnel provisioning.
        
        Returns:
            Tuple[success: bool, error_message: Optional[str], upstream_data: Optional[dict]]
        
        TODO: Replace with actual upstream endpoint when available.
        Current implementation simulates the call in DRY_RUN mode.
        If you have an actual upstream API:
        1. Update the endpoint URL below
        2. Adjust the request payload format
        3. Parse the upstream response appropriately
        """
        if self.dry_run:
            logger.info(f"DRY_RUN: Simulating VM provisioning for {user_email}")
            # Simulate successful provisioning with sample WireGuard config
            return True, None, {
                "upstream_id": "dry-run-vm-12345",
                "status": "provisioning",
                "message": "VM provisioning started (DRY_RUN mode)"
            }
        
        # TODO: Implement actual upstream API call
        # Example structure:
        try:
            url = f"{self.base_url}/provision"  # TODO: Update endpoint
            payload = {
                "user_email": user_email,
                "request_data": request_data
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code >= 400:
                error_msg = f"Upstream API error: {response.status_code}"
                logger.error(f"{error_msg} - {response.text}")
                return False, error_msg, None
            
            data = response.json()
            return True, None, data
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to call upstream API: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"Unexpected error calling upstream: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None
    
    def get_status(self, upstream_id: str) -> Tuple[bool, Optional[str], Optional[dict]]:
        """
        Poll upstream provider for job status.
        
        Returns:
            Tuple[success: bool, error_message: Optional[str], status_data: Optional[dict]]
        
        TODO: Replace with actual upstream status endpoint.
        Expected response format:
        {
            "status": "running|completed|failed",
            "progress": "description",
            "result": {...},  # present when completed
            "error": "..."    # present when failed
        }
        """
        if self.dry_run:
            logger.info(f"DRY_RUN: Getting status for {upstream_id}")
            # Simulate completed state with WireGuard config
            return True, None, {
                "status": "completed",
                "progress": "VM ready with WireGuard configured",
                "result": {
                    "vmName": "dry-run-vm-12345",
                    "publicIp": "203.0.113.42",
                    "confText": self._get_sample_config()
                }
            }
        
        # TODO: Implement actual upstream status check
        # Example structure:
        try:
            url = f"{self.base_url}/status/{upstream_id}"  # TODO: Update endpoint
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code == 404:
                return False, "Job not found on upstream", None
            
            if response.status_code >= 400:
                error_msg = f"Upstream API error: {response.status_code}"
                logger.error(f"{error_msg} - {response.text}")
                return False, error_msg, None
            
            data = response.json()
            return True, None, data
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to get status from upstream: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"Unexpected error getting upstream status: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None
    
    def _get_sample_config(self) -> str:
        """Generate sample WireGuard configuration for dry run."""
        return """[Interface]
PrivateKey = cOFA1gfMGvoDSJHKOlk5XaXDQZCOVAn3wR4SbQsXX3Q=
Address = 10.0.0.2/24
DNS = 8.8.8.8

[Peer]
PublicKey = n/fMKKDjMxKNvSZHQTWYUCYDcTGgTwMJkLc0X7rTgXo=
Endpoint = 203.0.113.42:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""


# Singleton instance
_provider_instance = None


def get_upstream_provider() -> UpstreamProvider:
    """Get the singleton upstream provider instance."""
    global _provider_instance
    
    if _provider_instance is None:
        _provider_instance = UpstreamProvider()
    
    return _provider_instance
