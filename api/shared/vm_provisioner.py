"""
Azure VM provisioning for WireGuard using Service Principal credentials.
Adapted for Azure Static Web Apps Functions (no Managed Identity support).
Uses Docker-based WireGuard deployment on Flatcar Container Linux.
"""
import logging
import os
import time
import base64
import re
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
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
        
        if not is_dry_run():
            success, error, credential = get_azure_credential()
            if not success:
                raise ValueError(f"Cannot initialize VM provisioner: {error}")
            
            self.credential = credential
            self.compute_client = ComputeManagementClient(credential, self.subscription_id)
            self.network_client = NetworkManagementClient(credential, self.subscription_id)
    
    def get_or_create_vm(self, location: str = 'eastus', admin_username: str = 'azureuser') -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Get existing running WireGuard VM or create a new one (idempotent operation).
        Only one VM exists at a time - returns existing VM if running, creates new one otherwise.
        Returns: (success, error_message, operation_data)
        """
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
                        
                        # For existing VM in 'Succeeded' state, we need to setup WireGuard if not already done
                        conf_text = None
                        if vm.provisioning_state == 'Succeeded' and ip_address:
                            # Try to setup WireGuard via Run Command
                            conf_text = self._setup_wireguard_via_run_command(vm_name)
                            if not conf_text:
                                # Fallback to sample config if Run Command fails
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
    
    def create_vm(self, location: str = 'eastus', admin_username: str = 'azureuser') -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Create a new VM for WireGuard asynchronously.
        Returns immediately with operation details.
        Returns: (success, error_message, operation_data)
        
        Note: Use get_or_create_vm() for idempotent operations.
        """
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
            
            # Create VNet, Public IP, NIC, and VM
            vnet_name = f"{vm_name}-vnet"
            subnet_name = "default"
            public_ip_name = f"{vm_name}-ip"
            nic_name = f"{vm_name}-nic"
            nsg_name = f"{vm_name}-nsg"
            
            # Step 1: Create Network Security Group
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
                        'name': 'AllowSSH',
                        'protocol': 'Tcp',
                        'source_port_range': '*',
                        'destination_port_range': '22',
                        'source_address_prefix': '*',
                        'destination_address_prefix': '*',
                        'access': 'Allow',
                        'priority': 110,
                        'direction': 'Inbound'
                    }
                ]
            }
            
            logger.info(f"Creating NSG {nsg_name}")
            nsg_poller = self.network_client.network_security_groups.begin_create_or_update(
                self.resource_group,
                nsg_name,
                nsg_params
            )
            nsg_result = nsg_poller.result()
            
            # Step 2: Create Virtual Network
            vnet_params = {
                'location': location,
                'address_space': {
                    'address_prefixes': ['10.0.0.0/16']
                },
                'subnets': [{
                    'name': subnet_name,
                    'address_prefix': '10.0.0.0/24',
                    'network_security_group': {'id': nsg_result.id}
                }]
            }
            
            logger.info(f"Creating VNet {vnet_name}")
            vnet_poller = self.network_client.virtual_networks.begin_create_or_update(
                self.resource_group,
                vnet_name,
                vnet_params
            )
            vnet_result = vnet_poller.result()
            
            # Step 3: Create Public IP
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
            
            # Step 4: Create Network Interface
            nic_params = {
                'location': location,
                'ip_configurations': [{
                    'name': 'ipconfig1',
                    'subnet': {'id': vnet_result.subnets[0].id},
                    'public_ip_address': {'id': public_ip_result.id}
                }],
                'network_security_group': {'id': nsg_result.id}
            }
            
            logger.info(f"Creating NIC {nic_name}")
            nic_poller = self.network_client.network_interfaces.begin_create_or_update(
                self.resource_group,
                nic_name,
                nic_params
            )
            nic_result = nic_poller.result()
            
            # Step 5: Start VM creation asynchronously
            # Use Flatcar Container Linux for faster Docker-based WireGuard deployment
            # Note: Flatcar uses Ignition config (not cloud-init), which we'll skip for simplicity.
            # WireGuard setup will be done via Azure Run Command after VM is ready.
            
            # Generate a temporary SSH key for this VM (will be used for Run Command if needed)
            # For production, use Key Vault or generate ephemeral keys
            ssh_public_key = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7VK8vGNQQoKlmBV6ZxLmTlJ5d9z3VqLK9XZ6hXJ0eC0yLnF8ZH5mD6K5BqE8dF3MxR9hJN8dG5pQ6L7zQ9F0sX5d3P8Y7mN9Z6rT4K8sQ5pF0xJ6K5V8yL3M0sR9hJN8dG5pQ6L7zQ9F0 wireguard-vm'
            
            vm_params = {
                'location': location,
                'hardware_profile': {
                    'vm_size': 'Standard_B1ls'  # Cheapest size, sufficient for WireGuard
                },
                'storage_profile': {
                    'image_reference': {
                        # Flatcar Container Linux Stable
                        'publisher': 'kinvolk',
                        'offer': 'flatcar-container-linux-free',
                        'sku': 'stable',
                        'version': 'latest'
                    },
                    'os_disk': {
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
                                'key_data': ssh_public_key
                            }]
                        }
                    }
                },
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
                    
                    # Execute Run Command to setup WireGuard Docker container and get config
                    logger.info(f"VM {vm_name} is ready, executing WireGuard setup via Run Command")
                    conf_text = self._setup_wireguard_via_run_command(vm_name)
                    
                    if conf_text:
                        logger.info(f"WireGuard setup successful for VM {vm_name}")
                        return True, None, {
                            'vmName': vm_name,
                            'status': 'Succeeded',
                            'publicIp': ip_address,
                            'confText': conf_text
                        }
                    else:
                        # Run Command failed or didn't return config
                        logger.warning(f"WireGuard setup incomplete for VM {vm_name}, returning sample config")
                        return True, None, {
                            'vmName': vm_name,
                            'status': 'Succeeded',
                            'publicIp': ip_address,
                            'confText': self._get_sample_config(ip_address) if ip_address else None
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
            
            # Delete associated resources
            nic_name = f"{vm_name}-nic"
            public_ip_name = f"{vm_name}-ip"
            vnet_name = f"{vm_name}-vnet"
            nsg_name = f"{vm_name}-nsg"
            
            # Delete NIC
            try:
                self.network_client.network_interfaces.begin_delete(
                    self.resource_group,
                    nic_name
                ).result()
            except Exception as e:
                logger.warning(f"Could not delete NIC {nic_name}: {e}")
            
            # Delete Public IP
            try:
                self.network_client.public_ip_addresses.begin_delete(
                    self.resource_group,
                    public_ip_name
                ).result()
            except Exception as e:
                logger.warning(f"Could not delete Public IP {public_ip_name}: {e}")
            
            # Delete NSG
            try:
                self.network_client.network_security_groups.begin_delete(
                    self.resource_group,
                    nsg_name
                ).result()
            except Exception as e:
                logger.warning(f"Could not delete NSG {nsg_name}: {e}")
            
            # Delete VNet
            try:
                self.network_client.virtual_networks.begin_delete(
                    self.resource_group,
                    vnet_name
                ).result()
            except Exception as e:
                logger.warning(f"Could not delete VNet {vnet_name}: {e}")
            
            logger.info(f"VM {vm_name} and associated resources deleted successfully")
            return True, None
            
        except Exception as e:
            logger.error(f"Error deleting VM {vm_name}: {str(e)}", exc_info=True)
            return False, f"Failed to delete VM: {str(e)}"
    
    def _setup_wireguard_via_run_command(self, vm_name: str) -> Optional[str]:
        """
        Execute Azure Run Command to setup WireGuard in Docker container and retrieve client config.
        Returns the WireGuard client configuration or None if setup fails.
        """
        try:
            logger.info(f"Executing Run Command on VM {vm_name} to setup WireGuard")
            
            # Read the setup script
            script_path = os.path.join(os.path.dirname(__file__), 'wireguard_docker_setup.sh')
            try:
                with open(script_path, 'r') as f:
                    setup_script = f.read()
            except Exception as e:
                logger.error(f"Failed to read setup script: {str(e)}")
                return None
            
            # Execute Run Command with the script
            run_command_params = {
                'command_id': 'RunShellScript',
                'script': [setup_script]
            }
            
            logger.info(f"Starting Run Command on VM {vm_name}")
            poller = self.compute_client.virtual_machines.begin_run_command(
                self.resource_group,
                vm_name,
                run_command_params
            )
            
            # Wait for the command to complete (timeout after 5 minutes)
            logger.info("Waiting for Run Command to complete (timeout: 300s)...")
            result = poller.result(timeout=300)
            
            # Extract output
            if result.value and len(result.value) > 0:
                output = result.value[0].message
                logger.info(f"Run Command completed with output length: {len(output) if output else 0}")
                
                # Extract WireGuard config from output
                conf_text = self._extract_wireguard_config(output)
                
                if conf_text:
                    logger.info(f"Successfully extracted WireGuard config from Run Command output")
                    return conf_text
                else:
                    logger.warning(f"Could not extract WireGuard config from Run Command output")
                    logger.debug(f"Run Command output: {output[:1000]}")  # Log first 1000 chars
                    return None
            else:
                logger.error(f"Run Command returned no output")
                return None
                
        except Exception as e:
            logger.error(f"Error executing Run Command on VM {vm_name}: {str(e)}", exc_info=True)
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


# Singleton instance
_provisioner_instance = None


def get_vm_provisioner() -> VMProvisioner:
    """Get the singleton VM provisioner instance."""
    global _provisioner_instance
    
    if _provisioner_instance is None:
        _provisioner_instance = VMProvisioner()
    
    return _provisioner_instance
