"""Durable Functions orchestrator for WireGuard VM lifecycle."""
import logging
import azure.functions as func
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    """Orchestrate WireGuard VM creation, monitoring, and cleanup."""
    logging.info("Starting WireGuard orchestration")
    
    # Get input from the starter
    input_data = context.get_input()
    user_email = input_data.get('user_email', 'unknown')
    session_duration = input_data.get('duration', 3600)  # Default 1 hour
    
    vm_name = f"wireguard-{context.instance_id[:8]}"
    
    try:
        # Step 1: Provision VM
        logging.info(f"Provisioning VM {vm_name} for user {user_email}")
        provision_result = yield context.call_activity('ProvisionVM', {
            'vm_name': vm_name,
            'user_email': user_email
        })
        
        # Step 2: Wait for session duration
        deadline = context.current_utc_datetime + context.create_timer_duration(session_duration)
        yield context.create_timer(deadline)
        
        # Step 3: Destroy VM
        logging.info(f"Session expired, destroying VM {vm_name}")
        destroy_result = yield context.call_activity('DestroyVM', {
            'vm_name': vm_name
        })
        
        return {
            'status': 'completed',
            'vm_name': vm_name,
            'user_email': user_email,
            'provision_result': provision_result,
            'destroy_result': destroy_result
        }
        
    except Exception as e:
        logging.error(f"Orchestration error: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

main = df.Orchestrator.create(orchestrator_function)
