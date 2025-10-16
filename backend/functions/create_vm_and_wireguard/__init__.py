"""
Activity function - Creates a VM and configures WireGuard.

In DRY_RUN mode: Returns a sample configuration without creating Azure resources.
In production mode: Provisions a minimal Ubuntu VM and installs/configures WireGuard.
"""
import logging
import os
import time
import base64
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from shared.wireguard import generate_sample_config, generate_client_config, generate_keypair

logger = logging.getLogger(__name__)


def main(activityInput: dict) -> dict:
    """
    Creates a VM and generates WireGuard configuration.
    
    Args:
        activityInput: Dictionary containing user_email and action
    
    Returns:
        dict: Contains confText, vmName, and resourceIds
    """
    user_email = activityInput.get('user_email', 'unknown')
    dry_run = os.environ.get('DRY_RUN', 'false').lower() == 'true'
    
    logger.info(f'create_vm_and_wireguard called for user: {user_email}, DRY_RUN={dry_run}')
    
    if dry_run:
        logger.info('DRY_RUN mode: Returning sample configuration')
        return create_dry_run_config(user_email)
    else:
        logger.info('Production mode: Creating real VM')
        return create_real_vm(user_email)


def create_dry_run_config(user_email: str) -> dict:
    """
    Creates a sample WireGuard configuration for testing without Azure resources.
    """
    try:
        # Generate a sample configuration
        sample_ip = "203.0.113.10"  # TEST-NET-3 (RFC 5737) - sample IP
        conf_text = generate_sample_config(sample_ip)
        
        # Simulate a small delay (as if we're provisioning)
        time.sleep(2)
        
        vm_name = f"wg-vm-dry-run-{int(time.time())}"
        
        logger.info(f'DRY_RUN: Generated sample config for {user_email}')
        
        return {
            'status': 'success',
            'confText': conf_text,
            'vmName': vm_name,
            'resourceIds': {
                'vm': f'/subscriptions/dry-run/resourceGroups/dry-run/providers/Microsoft.Compute/virtualMachines/{vm_name}',
                'nic': f'/subscriptions/dry-run/resourceGroups/dry-run/providers/Microsoft.Network/networkInterfaces/{vm_name}-nic',
                'publicIp': f'/subscriptions/dry-run/resourceGroups/dry-run/providers/Microsoft.Network/publicIPAddresses/{vm_name}-ip',
                'disk': f'/subscriptions/dry-run/resourceGroups/dry-run/providers/Microsoft.Compute/disks/{vm_name}-disk'
            },
            'dryRun': True
        }
    except Exception as e:
        logger.error(f'Error in DRY_RUN mode: {str(e)}', exc_info=True)
        return {
            'error': f'DRY_RUN configuration generation failed: {str(e)}'
        }


def create_real_vm(user_email: str) -> dict:
    """
    Creates a real Azure VM with WireGuard installed.
    
    TODO: Production hardening needed:
    - Add retry logic for Azure API calls
    - Implement proper error handling and rollback
    - Add network security group rules
    - Consider using cloud-init for WireGuard setup
    - Add monitoring and logging
    - Implement proper SSH key management
    """
    try:
        # Get Azure configuration from environment
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        resource_group = os.environ.get('AZURE_RESOURCE_GROUP')
        location = os.environ.get('AZURE_LOCATION', 'eastus')
        admin_username = os.environ.get('ADMIN_USERNAME', 'azureuser')
        
        if not all([subscription_id, resource_group]):
            raise ValueError('Missing required Azure configuration. Set AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP.')
        
        # Initialize Azure clients
        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, subscription_id)
        network_client = NetworkManagementClient(credential, subscription_id)
        
        # Generate unique VM name
        timestamp = int(time.time())
        vm_name = f"wg-vm-{timestamp}"
        
        logger.info(f'Creating VM {vm_name} in {resource_group}/{location}')
        
        # Step 1: Create public IP
        public_ip_params = {
            'location': location,
            'sku': {'name': 'Basic'},
            'public_ip_allocation_method': 'Dynamic'
        }
        
        logger.info('Creating public IP address...')
        public_ip_operation = network_client.public_ip_addresses.begin_create_or_update(
            resource_group,
            f'{vm_name}-ip',
            public_ip_params
        )
        public_ip = public_ip_operation.result()
        logger.info(f'Public IP created: {public_ip.id}')
        
        # Step 2: Create virtual network (or use existing)
        # TODO: For production, consider using a pre-existing VNet
        vnet_name = f'{vm_name}-vnet'
        subnet_name = 'default'
        
        vnet_params = {
            'location': location,
            'address_space': {
                'address_prefixes': ['10.0.0.0/16']
            },
            'subnets': [{
                'name': subnet_name,
                'address_prefix': '10.0.0.0/24'
            }]
        }
        
        logger.info('Creating virtual network...')
        vnet_operation = network_client.virtual_networks.begin_create_or_update(
            resource_group,
            vnet_name,
            vnet_params
        )
        vnet = vnet_operation.result()
        subnet = vnet.subnets[0]
        logger.info(f'VNet created: {vnet.id}')
        
        # Step 3: Create network interface
        nic_params = {
            'location': location,
            'ip_configurations': [{
                'name': 'ipconfig1',
                'subnet': {'id': subnet.id},
                'public_ip_address': {'id': public_ip.id}
            }]
        }
        
        logger.info('Creating network interface...')
        nic_operation = network_client.network_interfaces.begin_create_or_update(
            resource_group,
            f'{vm_name}-nic',
            nic_params
        )
        nic = nic_operation.result()
        logger.info(f'NIC created: {nic.id}')
        
        # Step 4: Create the VM
        # Using Standard_B1ls (cheapest option) for minimal cost
        vm_params = {
            'location': location,
            'hardware_profile': {
                'vm_size': 'Standard_B1ls'
            },
            'storage_profile': {
                'image_reference': {
                    'publisher': 'Canonical',
                    'offer': '0001-com-ubuntu-server-jammy',
                    'sku': '22_04-lts-gen2',
                    'version': 'latest'
                },
                'os_disk': {
                    'name': f'{vm_name}-disk',
                    'create_option': 'FromImage',
                    'managed_disk': {
                        'storage_account_type': 'Standard_LRS'
                    }
                }
            },
            'os_profile': {
                'computer_name': vm_name,
                'admin_username': admin_username,
                'linux_configuration': {
                    'disable_password_authentication': True,
                    'ssh': {
                        'public_keys': [{
                            'path': f'/home/{admin_username}/.ssh/authorized_keys',
                            'key_data': get_ssh_public_key()
                        }]
                    }
                }
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': nic.id
                }]
            }
        }
        
        logger.info('Creating VM (this may take several minutes)...')
        vm_operation = compute_client.virtual_machines.begin_create_or_update(
            resource_group,
            vm_name,
            vm_params
        )
        vm = vm_operation.result()
        logger.info(f'VM created: {vm.id}')
        
        # Step 5: Wait for public IP to be assigned
        logger.info('Waiting for public IP assignment...')
        max_retries = 30
        for i in range(max_retries):
            public_ip = network_client.public_ip_addresses.get(resource_group, f'{vm_name}-ip')
            if public_ip.ip_address:
                break
            time.sleep(5)
        
        if not public_ip.ip_address:
            raise Exception('Failed to get public IP address')
        
        server_ip = public_ip.ip_address
        logger.info(f'VM public IP: {server_ip}')
        
        # Step 6: Install and configure WireGuard
        # TODO: For production, use cloud-init or custom script extension
        # For now, we'll generate keys and return a configuration
        server_private, server_public = generate_keypair()
        conf_text, client_private, client_public = generate_client_config(server_public, server_ip)
        
        logger.info(f'WireGuard configuration generated for {user_email}')
        
        # TODO: Actually SSH into the VM and configure WireGuard server
        # For MVP, we're returning a client config that would work once server is set up
        
        return {
            'status': 'success',
            'confText': conf_text,
            'vmName': vm_name,
            'serverIp': server_ip,
            'resourceIds': {
                'vm': vm.id,
                'nic': nic.id,
                'publicIp': public_ip.id,
                'vnet': vnet.id,
                'disk': f'{vm.id}/disks/{vm_name}-disk'
            },
            'serverPublicKey': server_public,
            'clientPublicKey': client_public
        }
        
    except Exception as e:
        logger.error(f'Error creating VM: {str(e)}', exc_info=True)
        return {
            'error': f'VM creation failed: {str(e)}'
        }


def get_ssh_public_key() -> str:
    """
    Get SSH public key for VM access.
    
    TODO: For production, implement proper key management:
    - Store keys in Azure Key Vault
    - Support multiple keys or generate ephemeral keys
    - Add key rotation
    """
    # Try to get from environment (base64 encoded private key)
    # For MVP, we'll generate a placeholder key
    # In production, you'd derive public from private key stored in Key Vault
    
    # Placeholder - this should be a real SSH public key
    placeholder_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC... wireguard-vm"
    
    # TODO: Implement proper SSH key handling
    logger.warning('Using placeholder SSH key - TODO: Implement proper key management')
    
    return placeholder_key
