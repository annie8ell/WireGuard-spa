"""
Orchestrator function - Manages the WireGuard VPN lifecycle.

Flow:
1. Call activity to create VM and generate WireGuard config
2. Return config to user
3. Wait 30 minutes (durable timer)
4. Call activity to teardown VM
"""
import logging
import azure.durable_functions as df
from datetime import timedelta

logger = logging.getLogger(__name__)


def orchestrator_function(context: df.DurableOrchestrationContext):
    """
    Orchestrates the WireGuard VPN provisioning and teardown.
    
    Steps:
    1. Create VM and generate WireGuard configuration
    2. Return configuration to caller
    3. Wait 30 minutes
    4. Teardown VM and resources
    """
    orchestration_input = context.get_input()
    user_email = orchestration_input.get('user_email', 'unknown')
    
    logger.info(f'Orchestration started for user: {user_email}')
    
    try:
        # Step 1: Create VM and generate WireGuard config
        context.set_custom_status('Creating VM and generating WireGuard configuration...')
        
        vm_result = yield context.call_activity(
            'create_vm_and_wireguard',
            orchestration_input
        )
        
        # Check if VM creation was successful
        if not vm_result or 'error' in vm_result:
            error_msg = vm_result.get('error', 'Unknown error') if vm_result else 'VM creation returned no result'
            logger.error(f'VM creation failed: {error_msg}')
            return {
                'status': 'error',
                'error': error_msg
            }
        
        # Step 2: Extract configuration and return to caller
        conf_text = vm_result.get('confText')
        vm_name = vm_result.get('vmName', 'unknown')
        
        if not conf_text:
            logger.error('No configuration text in VM result')
            return {
                'status': 'error',
                'error': 'Configuration generation failed'
            }
        
        logger.info(f'VM {vm_name} created successfully for user {user_email}')
        
        # This is what gets returned to the HTTP caller
        result = {
            'status': 'ready',
            'confText': conf_text,
            'vmName': vm_name
        }
        
        # Step 3: Set up teardown after 30 minutes
        context.set_custom_status('VPN ready. Scheduled for teardown in 30 minutes.')
        
        # Create durable timer for 30 minutes
        teardown_at = context.current_utc_datetime + timedelta(minutes=30)
        yield context.create_timer(teardown_at)
        
        # Step 4: Teardown the VM
        context.set_custom_status('Tearing down VM...')
        logger.info(f'Starting teardown for VM {vm_name}')
        
        teardown_input = {
            'vmName': vm_name,
            'resourceIds': vm_result.get('resourceIds', {}),
            'user_email': user_email
        }
        
        teardown_result = yield context.call_activity(
            'teardown_vm',
            teardown_input
        )
        
        if teardown_result and teardown_result.get('status') == 'success':
            logger.info(f'VM {vm_name} teardown completed successfully')
            context.set_custom_status('Teardown completed.')
        else:
            logger.warning(f'VM {vm_name} teardown completed with warnings')
        
        # Return the original result (configuration) - this is what the HTTP caller sees
        return result
        
    except Exception as e:
        logger.error(f'Orchestration error: {str(e)}', exc_info=True)
        context.set_custom_status(f'Error: {str(e)}')
        return {
            'status': 'error',
            'error': str(e)
        }


main = df.Orchestrator.create(orchestrator_function)
