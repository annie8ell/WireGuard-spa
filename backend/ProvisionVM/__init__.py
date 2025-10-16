"""Activity function to provision a WireGuard VM."""
import logging
import azure.functions as func
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.vm_manager import VMManager

def main(payload: dict) -> dict:
    """Provision a new VM for WireGuard."""
    vm_name = payload.get('vm_name')
    user_email = payload.get('user_email')
    
    logging.info(f"Provisioning VM {vm_name} for user {user_email}")
    
    try:
        vm_manager = VMManager()
        result = vm_manager.create_vm(vm_name)
        
        logging.info(f"VM {vm_name} provisioned successfully")
        
        return {
            'status': 'success',
            'vm_name': vm_name,
            'public_ip': result.get('public_ip'),
            'user_email': user_email
        }
        
    except Exception as e:
        logging.error(f"Error provisioning VM: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }
