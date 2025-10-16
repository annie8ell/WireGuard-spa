"""Activity function to destroy a WireGuard VM."""
import logging
import azure.functions as func
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.vm_manager import VMManager

def main(payload: dict) -> dict:
    """Destroy a VM."""
    vm_name = payload.get('vm_name')
    
    logging.info(f"Destroying VM {vm_name}")
    
    try:
        vm_manager = VMManager()
        result = vm_manager.destroy_vm(vm_name)
        
        logging.info(f"VM {vm_name} destroyed successfully")
        
        return {
            'status': 'success',
            'vm_name': vm_name
        }
        
    except Exception as e:
        logging.error(f"Error destroying VM: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }
