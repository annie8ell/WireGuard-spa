"""
Activity function - Tears down the VM and associated resources.

In DRY_RUN mode: Logs the teardown without performing actual deletions.
In production mode: Deletes the VM, NIC, public IP, disk, and other resources.
"""
import logging
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


def main(activityInput: dict) -> dict:
    """
    Tears down the VM and all associated resources.
    
    Args:
        activityInput: Dictionary containing vmName, resourceIds, and user_email
    
    Returns:
        dict: Status of teardown operation
    """
    vm_name = activityInput.get('vmName', 'unknown')
    resource_ids = activityInput.get('resourceIds', {})
    user_email = activityInput.get('user_email', 'unknown')
    dry_run = os.environ.get('DRY_RUN', 'false').lower() == 'true'
    
    logger.info(f'teardown_vm called for VM: {vm_name}, user: {user_email}, DRY_RUN={dry_run}')
    
    if dry_run:
        logger.info(f'DRY_RUN mode: Simulating teardown of {vm_name}')
        return {
            'status': 'success',
            'message': f'DRY_RUN: Would have torn down VM {vm_name}',
            'vmName': vm_name,
            'dryRun': True
        }
    
    return teardown_real_vm(vm_name, resource_ids, user_email)


def teardown_real_vm(vm_name: str, resource_ids: dict, user_email: str) -> dict:
    """
    Deletes the VM and all associated Azure resources.
    
    TODO: Production hardening needed:
    - Add retry logic with exponential backoff
    - Handle partial failures gracefully
    - Add cleanup verification
    - Log all deletions for audit trail
    - Consider adding a safety check/confirmation
    """
    try:
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        resource_group = os.environ.get('AZURE_RESOURCE_GROUP')
        
        if not all([subscription_id, resource_group]):
            raise ValueError('Missing required Azure configuration')
        
        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, subscription_id)
        network_client = NetworkManagementClient(credential, subscription_id)
        
        deleted_resources = []
        failed_resources = []
        
        # Step 1: Delete the VM (this is the main resource)
        try:
            logger.info(f'Deleting VM: {vm_name}')
            vm_delete_operation = compute_client.virtual_machines.begin_delete(
                resource_group,
                vm_name
            )
            vm_delete_operation.wait()
            deleted_resources.append(f'VM: {vm_name}')
            logger.info(f'VM {vm_name} deleted successfully')
        except ResourceNotFoundError:
            logger.warning(f'VM {vm_name} not found, may have been already deleted')
        except Exception as e:
            error_msg = f'VM {vm_name}: {str(e)}'
            logger.error(f'Failed to delete VM: {error_msg}')
            failed_resources.append(error_msg)
        
        # Step 2: Delete network interface
        nic_name = f'{vm_name}-nic'
        try:
            logger.info(f'Deleting NIC: {nic_name}')
            nic_delete_operation = network_client.network_interfaces.begin_delete(
                resource_group,
                nic_name
            )
            nic_delete_operation.wait()
            deleted_resources.append(f'NIC: {nic_name}')
            logger.info(f'NIC {nic_name} deleted successfully')
        except ResourceNotFoundError:
            logger.warning(f'NIC {nic_name} not found')
        except Exception as e:
            error_msg = f'NIC {nic_name}: {str(e)}'
            logger.error(f'Failed to delete NIC: {error_msg}')
            failed_resources.append(error_msg)
        
        # Step 3: Delete public IP
        public_ip_name = f'{vm_name}-ip'
        try:
            logger.info(f'Deleting public IP: {public_ip_name}')
            ip_delete_operation = network_client.public_ip_addresses.begin_delete(
                resource_group,
                public_ip_name
            )
            ip_delete_operation.wait()
            deleted_resources.append(f'Public IP: {public_ip_name}')
            logger.info(f'Public IP {public_ip_name} deleted successfully')
        except ResourceNotFoundError:
            logger.warning(f'Public IP {public_ip_name} not found')
        except Exception as e:
            error_msg = f'Public IP {public_ip_name}: {str(e)}'
            logger.error(f'Failed to delete public IP: {error_msg}')
            failed_resources.append(error_msg)
        
        # Step 4: Delete virtual network (if it was created for this VM)
        vnet_name = f'{vm_name}-vnet'
        try:
            logger.info(f'Deleting VNet: {vnet_name}')
            vnet_delete_operation = network_client.virtual_networks.begin_delete(
                resource_group,
                vnet_name
            )
            vnet_delete_operation.wait()
            deleted_resources.append(f'VNet: {vnet_name}')
            logger.info(f'VNet {vnet_name} deleted successfully')
        except ResourceNotFoundError:
            logger.warning(f'VNet {vnet_name} not found')
        except Exception as e:
            error_msg = f'VNet {vnet_name}: {str(e)}'
            logger.error(f'Failed to delete VNet: {error_msg}')
            failed_resources.append(error_msg)
        
        # Step 5: Delete OS disk (usually deleted automatically with VM, but check)
        disk_name = f'{vm_name}-disk'
        try:
            logger.info(f'Checking/deleting disk: {disk_name}')
            disk_delete_operation = compute_client.disks.begin_delete(
                resource_group,
                disk_name
            )
            disk_delete_operation.wait()
            deleted_resources.append(f'Disk: {disk_name}')
            logger.info(f'Disk {disk_name} deleted successfully')
        except ResourceNotFoundError:
            logger.info(f'Disk {disk_name} not found (likely auto-deleted with VM)')
        except Exception as e:
            # Disk deletion errors are often benign (already deleted)
            logger.warning(f'Disk deletion note: {str(e)}')
        
        # Prepare result
        if failed_resources:
            logger.warning(f'Teardown completed with {len(failed_resources)} failures')
            return {
                'status': 'partial_success',
                'message': f'Deleted {len(deleted_resources)} resources, {len(failed_resources)} failed',
                'vmName': vm_name,
                'deleted': deleted_resources,
                'failed': failed_resources
            }
        else:
            logger.info(f'Teardown completed successfully for {vm_name}')
            return {
                'status': 'success',
                'message': f'All resources deleted successfully',
                'vmName': vm_name,
                'deleted': deleted_resources
            }
    
    except Exception as e:
        logger.error(f'Critical error during teardown: {str(e)}', exc_info=True)
        return {
            'status': 'error',
            'error': f'Teardown failed: {str(e)}',
            'vmName': vm_name
        }
