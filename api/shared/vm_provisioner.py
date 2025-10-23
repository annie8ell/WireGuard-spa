"""
Azure VM provisioning for WireGuard using Service Principal credentials.
Adapted for Azure Static Web Apps Functions (no Managed Identity support).
Uses Docker-based WireGuard deployment on Flatcar Container Linux.
"""
import logging
import os
import time
import base64
import json
import re
import io
import textwrap
import paramiko
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


def is_dry_run() -> bool:
    """Check if dry run mode is enabled."""
    return os.environ.get('DRY_RUN', 'false').lower() == 'true'


# Dry run state storage (in-memory for local development)
_dry_run_operations = {}


def get_dry_run_status(operation_id: str) -> Dict:
    """Get the status of a dry run operation with realistic timing."""
    current_time = time.time()
    
    if operation_id not in _dry_run_operations:
        # Initialize new operation
        _dry_run_operations[operation_id] = {
            'start_time': current_time,
            'status': 'Running',
            'public_ip': '203.0.113.42'
        }
    
    operation = _dry_run_operations[operation_id]
    elapsed = current_time - operation['start_time']
    
    # Simulate realistic provisioning timeline:
    # 0-3s: Creating
    # 3-8s: Running  
    # 8s+: Succeeded
    if elapsed < 3:
        operation['status'] = 'Creating'
    elif elapsed < 8:
        operation['status'] = 'Running'
    else:
        operation['status'] = 'Succeeded'
    
    return operation


def get_azure_credential() -> Tuple[bool, Optional[str], Optional[ClientSecretCredential]]:
    """
    Create Azure credential using Service Principal.
    Returns: (success, error_message, credential)
    """
    try:
        client_id = os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('AZURE_CLIENT_SECRET')
        tenant_id = os.environ.get('AZURE_TENANT_ID')
        
        if not all([client_id, client_secret, tenant_id]):
            return False, "Missing Azure credentials (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)", None
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        return True, None, credential
        
    except Exception as e:
        logger.error(f"Error creating Azure credential: {str(e)}", exc_info=True)
        return False, f"Failed to create Azure credential: {str(e)}", None


class VMProvisioner:
    """Provisions and manages Azure VMs for WireGuard."""
    
    def __init__(self):
        self.subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID', '')
        self.resource_group = os.environ.get('AZURE_RESOURCE_GROUP', '')
        
        # Cache the resource group location
        self._resource_group_location = None
        # Cache shared network resources
        self._shared_vnet = None
        self._shared_nsg = None
        
        if not is_dry_run():
            success, error, credential = get_azure_credential()
            if not success:
                raise ValueError(f"Cannot initialize VM provisioner: {error}")
            
            self.credential = credential
            self.compute_client = ComputeManagementClient(credential, self.subscription_id)
            self.network_client = NetworkManagementClient(credential, self.subscription_id)
    
    def _get_resource_group_location(self) -> str:
        """Get the location of the resource group."""
        if self._resource_group_location:
            return self._resource_group_location
        
        if is_dry_run():
            # For dry run, default to westeurope since that's what the user specified
            return 'westeurope'
        
        try:
            resource_client = ResourceManagementClient(self.credential, self.subscription_id)
            rg = resource_client.resource_groups.get(self.resource_group)
            self._resource_group_location = rg.location
            return self._resource_group_location
        except Exception as e:
            logger.warning(f"Could not get resource group location, defaulting to westeurope: {e}")
            return 'westeurope'
    
    def _get_or_create_shared_network_resources(self, location: str):
        """Get or create shared network resources (VNet and NSG) that can be reused across VMs."""
        if self._shared_vnet and self._shared_nsg:
            return self._shared_vnet, self._shared_nsg
        
        if is_dry_run():
            logger.info("DRY RUN: Would get or create shared network resources")
            # Mock shared resources for dry run
            self._shared_vnet = {'name': 'wireguard-shared-vnet', 'subnets': [{'id': 'mock-subnet-id'}]}
            self._shared_nsg = {'id': 'mock-nsg-id'}
            return self._shared_vnet, self._shared_nsg
        
        try:
            # Shared resource names
            shared_vnet_name = 'wireguard-shared-vnet'
            shared_nsg_name = 'wireguard-shared-nsg'
            
            # Check if NSG exists
            try:
                nsg = self.network_client.network_security_groups.get(
                    self.resource_group,
                    shared_nsg_name
                )
                logger.info(f"Using existing shared NSG: {shared_nsg_name}")
                self._shared_nsg = nsg
            except Exception:
                # Create NSG
                logger.info(f"Creating shared NSG: {shared_nsg_name}")
                nsg_params = {
                    'location': location,
                    'security_rules': [
                        {
                            'name': 'AllowWireGuard',
                            'protocol': 'Udp',
                            'source_port_range': '*',
                            'destination_port_range': '51820',
                            'source_address_prefix': '*',
                            'destination_address_prefix': '*',
                            'access': 'Allow',
                            'priority': 100,
                            'direction': 'Inbound'
                        },
                        {
                            'name': 'AllowSSHFromFunctions',
                            'protocol': 'Tcp',
                            'source_port_range': '*',
                            'destination_port_range': '22',
                            'source_address_prefixes': [
                                '20.38.64.0/19',
                                '20.39.0.0/16', 
                                '20.40.0.0/13',
                                '20.48.0.0/12',
                                '20.64.0.0/10'
                            ],
                            'destination_address_prefix': '*',
                            'access': 'Allow',
                            'priority': 110,
                            'direction': 'Inbound'
                        }
                    ]
                }
                
                nsg_poller = self.network_client.network_security_groups.begin_create_or_update(
                    self.resource_group,
                    shared_nsg_name,
                    nsg_params
                )
                self._shared_nsg = nsg_poller.result()
                logger.info(f"Created shared NSG: {shared_nsg_name}")
            
            # Check if VNet exists
            try:
                vnet = self.network_client.virtual_networks.get(
                    self.resource_group,
                    shared_vnet_name
                )
                logger.info(f"Using existing shared VNet: {shared_vnet_name}")
                self._shared_vnet = vnet
            except Exception:
                # Create VNet
                logger.info(f"Creating shared VNet: {shared_vnet_name}")
                vnet_params = {
                    'location': location,
                    'address_space': {
                        'address_prefixes': ['10.0.0.0/16']
                    },
                    'subnets': [{
                        'name': 'default',
                        'address_prefix': '10.0.0.0/24',
                        'network_security_group': {'id': self._shared_nsg.id}
                    }]
                }
                
                vnet_poller = self.network_client.virtual_networks.begin_create_or_update(
                    self.resource_group,
                    shared_vnet_name,
                    vnet_params
                )
                self._shared_vnet = vnet_poller.result()
                logger.info(f"Created shared VNet: {shared_vnet_name}")
            
            return self._shared_vnet, self._shared_nsg
            
        except Exception as e:
            logger.error(f"Error creating/getting shared network resources: {str(e)}", exc_info=True)
            raise
    
    def get_or_create_vm(self, location: str = None, admin_username: str = 'azureuser') -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Get existing running WireGuard VM or create a new one (idempotent operation).
        Only one VM exists at a time - returns existing VM if running, creates new one otherwise.
        Returns: (success, error_message, operation_data)
        """
        # Use resource group location if not specified
        if location is None:
            location = self._get_resource_group_location()
        
        if is_dry_run():
            logger.info(f"DRY RUN: Would get or create VM")
            # In dry run, initialize operation and return as "accepted"
            operation_id = f"dry-run-{int(time.time())}"
            get_dry_run_status(operation_id)  # Initialize the operation
            return True, None, {
                'vmName': f'wg-{int(time.time())}',
                'operationId': operation_id,
                'status': 'Creating',  # Start as creating
                'publicIp': None,  # No IP yet
                'location': location,
                'confText': None,  # No config yet
                'isExisting': False
            }
        
        try:
            # Check for existing VMs with wireguard tags
            logger.info("Checking for existing WireGuard VM")
            vms = self.compute_client.virtual_machines.list(self.resource_group)
            
            for vm in vms:
                # Check if this is a WireGuard VM
                if vm.tags and vm.tags.get('purpose') == 'wireguard-vpn':
                    vm_name = vm.name
                    logger.info(f"Found existing WireGuard VM: {vm_name}")
                    
                    # Check if it's running/succeeded
                    if vm.provisioning_state in ['Succeeded', 'Creating', 'Updating']:
                        # Return existing VM
                        public_ip_name = f"{vm_name}-ip"
                        try:
                            public_ip = self.network_client.public_ip_addresses.get(
                                self.resource_group,
                                public_ip_name
                            )
                            ip_address = public_ip.ip_address
                        except Exception:
                            ip_address = None
                        
                        # For existing VM in 'Succeeded' state, retrieve the generated WireGuard config
                        conf_text = None
                        if vm.provisioning_state == 'Succeeded' and ip_address:
                            # Retrieve WireGuard config via Run Command
                            conf_text = self._retrieve_wireguard_config_via_run_command(vm_name)
                            if not conf_text:
                                # Fallback to sample config if retrieval fails
                                conf_text = self._get_sample_config(ip_address)
                        
                        return True, None, {
                            'vmName': vm_name,
                            'operationId': vm_name,
                            'status': vm.provisioning_state,
                            'location': vm.location,
                            'publicIp': ip_address,
                            'publicIpName': public_ip_name,
                            'resourceGroup': self.resource_group,
                            'confText': conf_text,
                            'isExisting': True
                        }
            
            # No existing VM found, create a new one
            logger.info("No existing WireGuard VM found, creating new one")
            return self.create_vm(location, admin_username)
            
        except Exception as e:
            logger.error(f"Error in get_or_create_vm: {str(e)}", exc_info=True)
            return False, f"Failed to get or create VM: {str(e)}", None
    
    def create_vm(self, location: str = None, admin_username: str = 'azureuser') -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Create a new VM for WireGuard asynchronously.
        Returns immediately with operation details.
        Returns: (success, error_message, operation_data)
        
        Note: Use get_or_create_vm() for idempotent operations.
        """
        # Use resource group location if not specified
        if location is None:
            location = self._get_resource_group_location()
        
        # Generate unique VM name
        import time
        vm_name = f"wg-{int(time.time())}"
        
        if is_dry_run():
            logger.info(f"DRY RUN: Would create VM {vm_name} in {location}")
            # In dry run, initialize operation and return as "creating"
            operation_id = f"dry-run-{vm_name}"
            get_dry_run_status(operation_id)  # Initialize the operation
            return True, None, {
                'vmName': vm_name,
                'operationId': operation_id,
                'status': 'Creating',  # Start as creating
                'publicIp': None,  # No IP yet
                'location': location,
                'confText': None,  # No config yet
                'isExisting': False
            }
        
        try:
            logger.info(f"Starting async VM creation for {vm_name} in {location}")
            
            # Get or create shared network resources (VNet and NSG)
            shared_vnet, shared_nsg = self._get_or_create_shared_network_resources(location)
            
            # Create VM-specific resources (Public IP and NIC)
            public_ip_name = f"{vm_name}-ip"
            nic_name = f"{vm_name}-nic"
            
            # Step 1: Create Public IP
            public_ip_params = {
                'location': location,
                'sku': {'name': 'Standard'},
                'public_ip_allocation_method': 'Static'
            }
            
            logger.info(f"Creating Public IP {public_ip_name}")
            public_ip_poller = self.network_client.public_ip_addresses.begin_create_or_update(
                self.resource_group,
                public_ip_name,
                public_ip_params
            )
            public_ip_result = public_ip_poller.result()
            
            # Step 2: Create Network Interface using shared VNet and NSG
            nic_params = {
                'location': location,
                'ip_configurations': [{
                    'name': 'ipconfig1',
                    'subnet': {'id': shared_vnet.subnets[0].id},
                    'public_ip_address': {'id': public_ip_result.id}
                }],
                'network_security_group': {'id': shared_nsg.id}
            }
            
            logger.info(f"Creating NIC {nic_name}")
            nic_poller = self.network_client.network_interfaces.begin_create_or_update(
                self.resource_group,
                nic_name,
                nic_params
            )
            nic_result = nic_poller.result()
            
            # Step 5: Start VM creation asynchronously
            # Use Ubuntu 22.04 LTS for reliable cloud-init support and Docker compatibility
            # This avoids Flatcar's Ignition provisioning issues on Azure

            # Create cloud-init configuration that sets up WireGuard during boot
            cloud_init_config = self._generate_cloud_init_config()

            # Build os_profile supporting either SSH public key or admin password
            ssh_pub_key = os.environ.get('SSH_PUBLIC_KEY')
            admin_password = os.environ.get('AZURE_ADMIN_PASSWORD')

            if not ssh_pub_key and not admin_password:
                # Azure requires either SSH key or password enabled for Linux VMs
                return False, "Missing SSH_PUBLIC_KEY or AZURE_ADMIN_PASSWORD for Linux VM authentication", None

            os_profile = {
                'computer_name': vm_name,
                'admin_username': admin_username,
            }

            # If admin password provided, enable password auth
            if admin_password:
                os_profile['admin_password'] = admin_password
                linux_configuration = {
                    'disable_password_authentication': False
                }
            else:
                # Use SSH public key
                linux_configuration = {
                    'disable_password_authentication': True,
                    'ssh': {
                        'public_keys': [
                            {
                                'path': f"/home/{admin_username}/.ssh/authorized_keys",
                                'key_data': ssh_pub_key
                            }
                        ]
                    }
                }

            vm_params = {
                'location': location,
                'hardware_profile': {
                    'vm_size': 'Standard_B1ls'  # Cheapest size, sufficient for WireGuard
                },
                'storage_profile': {
                    'image_reference': {
                        # Ubuntu 22.04 LTS for reliable cloud-init support and Docker compatibility
                        # This avoids Flatcar's Ignition provisioning issues on Azure
                        'publisher': 'Canonical',
                        'offer': '0001-com-ubuntu-server-jammy',
                        'sku': '22_04-lts-gen2',
                        'version': 'latest'
                    },
                    'os_disk': {
                        'create_option': 'FromImage',
                        'managed_disk': {
                            'storage_account_type': 'Standard_LRS'
                        }
                    }
                },
                'os_profile': os_profile,
                'network_profile': {
                    'network_interfaces': [{
                        'id': nic_result.id
                    }]
                },
                'tags': {
                    'purpose': 'wireguard-vpn',
                    'auto-delete': 'true',
                    'created-by': 'wireguard-spa'
                }
            }

            # Add cloud-init config as customData for Ubuntu Linux
            if cloud_init_config:
                vm_params['os_profile']['customData'] = base64.b64encode(
                    cloud_init_config.encode('utf-8')
                ).decode('utf-8')
            
            logger.info(f"Starting async VM creation for {vm_name}")
            # Start the operation but don't wait for it to complete
            vm_poller = self.compute_client.virtual_machines.begin_create_or_update(
                self.resource_group,
                vm_name,
                vm_params
            )
            
            # Return immediately with operation details
            return True, None, {
                'vmName': vm_name,
                'operationId': vm_name,  # Use VM name as operation ID for status queries
                'status': 'InProgress',
                'location': location,
                'publicIpName': public_ip_name,
                'resourceGroup': self.resource_group
            }
            
        except Exception as e:
            logger.error(f"Error starting VM creation for {vm_name}: {str(e)}", exc_info=True)
            return False, f"Failed to start VM creation: {str(e)}", None
    
    def get_vm_status(self, vm_name: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Get the current status of a VM creation operation.
        When VM is 'Succeeded', execute Run Command to setup WireGuard in Docker and get client config.
        Returns: (success, error_message, status_data)
        """
        if is_dry_run():
            logger.info(f"DRY RUN: Getting status for VM {vm_name}")
            # Get realistic status based on elapsed time
            operation = get_dry_run_status(vm_name)
            status = operation['status']
            
            response = {
                'vmName': vm_name,
                'status': status,
            }
            
            if status == 'Succeeded':
                response.update({
                    'publicIp': operation['public_ip'],
                    'confText': self._get_sample_config(operation['public_ip'])
                })
            
            return True, None, response
        
        try:
            logger.info(f"Checking status for VM {vm_name}")
            
            # Try to get the VM
            try:
                vm = self.compute_client.virtual_machines.get(
                    self.resource_group,
                    vm_name,
                    expand='instanceView'
                )
                
                # VM exists, check its provisioning state
                provisioning_state = vm.provisioning_state
                
                if provisioning_state == 'Succeeded':
                    # Get the public IP
                    public_ip_name = f"{vm_name}-ip"
                    try:
                        public_ip = self.network_client.public_ip_addresses.get(
                            self.resource_group,
                            public_ip_name
                        )
                        ip_address = public_ip.ip_address
                    except Exception:
                        ip_address = None
                    
                    # VM is ready, WireGuard should be set up via Ignition systemd service
                    # Use Run Command to retrieve the generated client config
                    logger.info(f"VM {vm_name} is ready, retrieving WireGuard config via Run Command")
                    conf_text = self._retrieve_wireguard_config_via_run_command(vm_name)
                    
                    if conf_text:
                        # Replace placeholder IP with actual public IP if needed
                        if "REPLACE_WITH_PUBLIC_IP" in conf_text or conf_text.startswith("[Interface]"):
                            conf_text = conf_text.replace("REPLACE_WITH_PUBLIC_IP", ip_address)
                            # Also fix cases where IP detection failed and we have just ":51820"
                            if ":51820" in conf_text and not ip_address in conf_text:
                                conf_text = conf_text.replace(":51820", f"{ip_address}:51820")
                        
                        logger.info(f"WireGuard setup successful for VM {vm_name}")
                        return True, None, {
                            'vmName': vm_name,
                            'status': 'Succeeded',
                            'publicIp': ip_address,
                            'confText': conf_text
                        }
                    else:
                        # Setup failed
                        logger.error(f"WireGuard setup failed for VM {vm_name}")
                        return True, None, {
                            'vmName': vm_name,
                            'status': 'Failed',
                            'error': 'WireGuard setup failed',
                            'publicIp': ip_address
                        }
                elif provisioning_state in ['Creating', 'Updating']:
                    return True, None, {
                        'vmName': vm_name,
                        'status': 'InProgress',
                        'progress': f'VM provisioning state: {provisioning_state}'
                    }
                elif provisioning_state == 'Failed':
                    # Get error details if available
                    error_msg = "VM provisioning failed"
                    if vm.instance_view and vm.instance_view.statuses:
                        for status in vm.instance_view.statuses:
                            if status.level == 'Error':
                                error_msg = status.message or error_msg
                    
                    return True, None, {
                        'vmName': vm_name,
                        'status': 'Failed',
                        'error': error_msg
                    }
                else:
                    return True, None, {
                        'vmName': vm_name,
                        'status': provisioning_state,
                        'progress': f'VM state: {provisioning_state}'
                    }
                    
            except Exception as get_error:
                # VM doesn't exist yet or other error
                error_str = str(get_error)
                if 'ResourceNotFound' in error_str or 'NotFound' in error_str:
                    # VM creation might still be in progress
                    return True, None, {
                        'vmName': vm_name,
                        'status': 'InProgress',
                        'progress': 'VM creation in progress (resource not yet visible)'
                    }
                else:
                    # Some other error
                    logger.error(f"Error getting VM status: {error_str}")
                    return False, f"Error querying VM status: {error_str}", None
            
        except Exception as e:
            logger.error(f"Error checking VM status for {vm_name}: {str(e)}", exc_info=True)
            return False, f"Failed to check VM status: {str(e)}", None
    
    def delete_vm(self, vm_name: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a VM and all its associated resources.
        Returns: (success, error_message)
        """
        if is_dry_run():
            logger.info(f"DRY RUN: Would delete VM {vm_name}")
            return True, None
        
        try:
            logger.info(f"Deleting VM {vm_name}")
            
            # Delete VM
            self.compute_client.virtual_machines.begin_delete(
                self.resource_group,
                vm_name
            ).result()
            
            # Delete VM-specific resources (keep shared VNet and NSG)
            nic_name = f"{vm_name}-nic"
            public_ip_name = f"{vm_name}-ip"
            
            # Delete NIC
            try:
                self.network_client.network_interfaces.begin_delete(
                    self.resource_group,
                    nic_name
                ).result()
                logger.info(f"Deleted NIC {nic_name}")
            except Exception as e:
                logger.warning(f"Could not delete NIC {nic_name}: {e}")
            
            # Delete Public IP
            try:
                self.network_client.public_ip_addresses.begin_delete(
                    self.resource_group,
                    public_ip_name
                ).result()
                logger.info(f"Deleted Public IP {public_ip_name}")
            except Exception as e:
                logger.warning(f"Could not delete Public IP {public_ip_name}: {e}")
            
            logger.info(f"VM {vm_name} and VM-specific resources deleted successfully (shared network resources preserved)")
            return True, None
            
        except Exception as e:
            logger.error(f"Error deleting VM {vm_name}: {str(e)}", exc_info=True)
            return False, f"Failed to delete VM: {str(e)}"
    
    def _retrieve_wireguard_config_via_run_command(self, vm_name: str) -> Optional[str]:
        """
        Execute Azure Run Command to retrieve the generated WireGuard client config.
        WireGuard setup happens during VM boot, this only retrieves the config.
        Returns the WireGuard client configuration or None if retrieval fails.
        """
        try:
            logger.info(f"Executing Run Command on VM {vm_name} to retrieve WireGuard config")
            
            # Simple script to read the generated config
            retrieve_script = """#!/bin/bash
# Read the client config that was generated during boot by the WireGuard setup script
if [ -f /etc/wireguard/client.conf ]; then
    cat /etc/wireguard/client.conf
else
    echo "ERROR: Client config not found at /etc/wireguard/client.conf. Setup may still be in progress."
    exit 1
fi
"""
            
            # Execute Run Command
            run_command_params = {
                'command_id': 'RunShellScript',
                'script': retrieve_script.split('\n')
            }
            
            logger.info(f"Starting Run Command on VM {vm_name}")
            poller = self.compute_client.virtual_machines.begin_run_command(
                self.resource_group,
                vm_name,
                run_command_params
            )
            
            # Wait for the command to complete (timeout after 1 minute, retrieval is fast)
            logger.info("Waiting for Run Command to complete (timeout: 60s)...")
            result = poller.result(timeout=60)
            
            # Extract output
            if result.value and len(result.value) > 0:
                output = result.value[0].message
                logger.info(f"Run Command completed with output length: {len(output) if output else 0}")
                
                # Extract WireGuard config from output
                conf_text = self._extract_wireguard_config(output)
                
                if conf_text:
                    logger.info(f"Successfully retrieved WireGuard config from VM")
                    return conf_text
                else:
                    logger.warning(f"Could not extract WireGuard config from output")
                    logger.debug(f"Run Command output: {output[:500]}")
                    return None
            else:
                logger.error(f"Run Command returned no output")
                return None
                
        except Exception as e:
            logger.error(f"Error executing Run Command on VM {vm_name}: {str(e)}", exc_info=True)
            return None
    
    def _setup_wireguard_via_ssh(self, vm_name: str, ip_address: str) -> Optional[str]:
        """
        Setup WireGuard on VM via SSH and retrieve the client config.
        Executes the wireguard setup script on the VM and returns the generated client configuration.
        Returns the WireGuard client configuration or None if setup fails.
        """
        try:
            logger.info(f"Connecting via SSH to {ip_address} to setup WireGuard")
            
            # Get SSH key from environment
            ssh_private_key_b64 = os.environ.get('SSH_PRIVATE_KEY')
            if not ssh_private_key_b64:
                logger.error("SSH_PRIVATE_KEY environment variable not set")
                return None
            
            # Decode the base64 private key
            try:
                ssh_private_key = base64.b64decode(ssh_private_key_b64).decode('utf-8')
            except Exception as e:
                logger.error(f"Failed to decode SSH private key: {str(e)}")
                return None
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key
            private_key = paramiko.RSAKey.from_private_key(io.StringIO(ssh_private_key))
            
            # Connect to VM
            logger.info(f"SSH connecting to azureuser@{ip_address}")
            ssh.connect(
                hostname=ip_address,
                username='azureuser',
                pkey=private_key,
                timeout=30
            )
            
            # Execute the WireGuard setup script
            setup_script_path = os.path.join(os.path.dirname(__file__), 'wireguard_docker_setup.sh')
            with open(setup_script_path, 'r') as f:
                setup_script = f.read()
            
            # Execute setup script
            logger.info("Running WireGuard setup script via SSH")
            stdin, stdout, stderr = ssh.exec_command(setup_script)
            
            # Read output
            output = stdout.read().decode('utf-8')
            error_output = stderr.read().decode('utf-8')
            
            # Close connection
            ssh.close()
            
            if error_output:
                logger.warning(f"SSH setup script produced stderr: {error_output}")
            
            if output:
                logger.info(f"WireGuard setup completed via SSH")
                
                # Extract WireGuard config from output
                conf_text = self._extract_wireguard_config(output)
                
                if conf_text:
                    return conf_text
                else:
                    logger.warning("Could not extract WireGuard config from SSH setup output")
                    return None
            else:
                logger.error("SSH setup script returned no output")
                return None
                
        except Exception as e:
            logger.error(f"Error setting up WireGuard via SSH on VM {vm_name}: {str(e)}", exc_info=True)
            return None
    
    def _extract_wireguard_config(self, output: str) -> Optional[str]:
        """
        Extract WireGuard client configuration from Run Command output.
        Looks for text between markers: === WIREGUARD_CLIENT_CONFIG_START === and === WIREGUARD_CLIENT_CONFIG_END ===
        """
        try:
            # Find the config section in the output
            start_marker = "=== WIREGUARD_CLIENT_CONFIG_START ==="
            end_marker = "=== WIREGUARD_CLIENT_CONFIG_END ==="
            
            start_idx = output.find(start_marker)
            end_idx = output.find(end_marker)
            
            if start_idx != -1 and end_idx != -1:
                # Extract the config text between markers
                config_text = output[start_idx + len(start_marker):end_idx].strip()
                
                # Validate that it looks like a WireGuard config
                if '[Interface]' in config_text and '[Peer]' in config_text:
                    return config_text
                else:
                    logger.warning("Extracted text doesn't look like a valid WireGuard config")
                    return None
            else:
                logger.warning(f"Could not find config markers in output (start: {start_idx}, end: {end_idx})")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting WireGuard config: {str(e)}", exc_info=True)
            return None
    
    def _get_sample_config(self, public_ip: str = '203.0.113.42') -> str:
        """Generate sample WireGuard configuration (fallback)."""
        return f"""[Interface]
PrivateKey = cOFA1gfMGvoDSJHKOlk5XaXDQZCOVAn3wR4SbQsXX3Q=
Address = 10.13.13.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = n/fMKKDjMxKNvSZHQTWYUCYDcTGgTwMJkLc0X7rTgXo=
Endpoint = {public_ip}:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""

    def _generate_ignition_config(self) -> str:
        """
        Generate Ignition configuration for Flatcar Linux.
        Creates a systemd service that runs after network is online to set up WireGuard.
        Returns the Ignition JSON configuration as a string.
        """
        try:
            ignition_file = os.path.join(os.path.dirname(__file__), '..', 'wireguard-ignition.json')
            with open(ignition_file, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading Ignition config: {str(e)}")
            return None
    
    def _generate_cloud_init_config(self) -> str:
        """
        Generate cloud-init configuration that writes and runs the WireGuard Docker setup script.
        Returns the cloud-init YAML configuration as a string.
        Notes:
        - We embed the content of 'wireguard_docker_setup.sh' to keep a single source of truth.
        - The script saves the client config at /etc/wireguard/client.conf with extractable markers.
        """
        try:
            script_path = os.path.join(os.path.dirname(__file__), 'wireguard_docker_setup.sh')
            with open(script_path, 'r') as f:
                script_content = f.read().rstrip('\n')

            # Indent script content for cloud-init write_files block
            indented_script = textwrap.indent(script_content, ' ' * 6)

            cloud_config = f"""#cloud-config

write_files:
  - path: /usr/local/bin/wireguard_docker_setup.sh
    permissions: '0755'
    content: |
{indented_script}

runcmd:
  - [ bash, -c, "/usr/local/bin/wireguard_docker_setup.sh" ]
"""
            return cloud_config
        except Exception as e:
            logger.error(f"Error generating cloud-init config from script: {str(e)}", exc_info=True)
            return None


# Singleton instance
_provisioner_instance = None


def get_vm_provisioner() -> VMProvisioner:
    """Get the singleton VM provisioner instance."""
    global _provisioner_instance
    
    if _provisioner_instance is None:
        _provisioner_instance = VMProvisioner()
    
    return _provisioner_instance
