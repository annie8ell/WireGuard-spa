"""
Azure VM provisioning for WireGuard using Service Principal credentials.
Adapted for Azure Static Web Apps Functions (no Managed Identity support).
"""
import logging
import os
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


def is_dry_run() -> bool:
    """Check if dry run mode is enabled."""
    return os.environ.get('DRY_RUN', 'false').lower() == 'true'


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
    
    def create_vm(self, vm_name: str, location: str = 'eastus', admin_username: str = 'azureuser') -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Create a new VM for WireGuard.
        Returns: (success, error_message, vm_data)
        """
        if is_dry_run():
            logger.info(f"DRY RUN: Would create VM {vm_name} in {location}")
            return True, None, {
                'vmName': vm_name,
                'publicIp': '203.0.113.42',
                'location': location,
                'status': 'dry_run',
                'confText': self._get_sample_config()
            }
        
        try:
            logger.info(f"Creating VM {vm_name} in {location}")
            
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
            nsg_result = self.network_client.network_security_groups.begin_create_or_update(
                self.resource_group,
                nsg_name,
                nsg_params
            ).result()
            
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
            vnet_result = self.network_client.virtual_networks.begin_create_or_update(
                self.resource_group,
                vnet_name,
                vnet_params
            ).result()
            
            # Step 3: Create Public IP
            public_ip_params = {
                'location': location,
                'sku': {'name': 'Standard'},
                'public_ip_allocation_method': 'Static'
            }
            
            logger.info(f"Creating Public IP {public_ip_name}")
            public_ip_result = self.network_client.public_ip_addresses.begin_create_or_update(
                self.resource_group,
                public_ip_name,
                public_ip_params
            ).result()
            
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
            nic_result = self.network_client.network_interfaces.begin_create_or_update(
                self.resource_group,
                nic_name,
                nic_params
            ).result()
            
            # Step 5: Create VM with cloud-init script for WireGuard
            # TODO: Generate actual WireGuard keys and configuration
            # For now, using placeholder
            cloud_init_script = """#cloud-config
package_upgrade: true
packages:
  - wireguard

runcmd:
  - echo "WireGuard installation complete" > /var/log/wireguard-setup.log
"""
            
            vm_params = {
                'location': location,
                'hardware_profile': {
                    'vm_size': 'Standard_B1ls'  # Cheapest size
                },
                'storage_profile': {
                    'image_reference': {
                        'publisher': 'Canonical',
                        'offer': 'UbuntuServer',
                        'sku': '18.04-LTS',
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
                    'custom_data': cloud_init_script,
                    'linux_configuration': {
                        'disable_password_authentication': True,
                        'ssh': {
                            'public_keys': [{
                                'path': f'/home/{admin_username}/.ssh/authorized_keys',
                                'key_data': 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... placeholder'  # TODO: Use Key Vault
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
            
            logger.info(f"Creating VM {vm_name}")
            vm_result = self.compute_client.virtual_machines.begin_create_or_update(
                self.resource_group,
                vm_name,
                vm_params
            ).result()
            
            # Get the public IP address
            public_ip = self.network_client.public_ip_addresses.get(
                self.resource_group,
                public_ip_name
            )
            
            logger.info(f"VM {vm_name} created successfully with IP {public_ip.ip_address}")
            
            # TODO: Generate actual WireGuard configuration
            # For now, return placeholder
            return True, None, {
                'vmName': vm_name,
                'publicIp': public_ip.ip_address,
                'location': location,
                'status': 'provisioned',
                'confText': self._get_sample_config(public_ip.ip_address),
                'resourceIds': {
                    'vm': vm_result.id,
                    'nic': nic_result.id,
                    'publicIp': public_ip.id,
                    'vnet': vnet_result.id,
                    'nsg': nsg_result.id
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating VM {vm_name}: {str(e)}", exc_info=True)
            return False, f"Failed to create VM: {str(e)}", None
    
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
    
    def _get_sample_config(self, public_ip: str = '203.0.113.42') -> str:
        """Generate sample WireGuard configuration."""
        # TODO: Generate actual keys and configuration
        return f"""[Interface]
PrivateKey = cOFA1gfMGvoDSJHKOlk5XaXDQZCOVAn3wR4SbQsXX3Q=
Address = 10.0.0.2/24
DNS = 8.8.8.8

[Peer]
PublicKey = n/fMKKDjMxKNvSZHQTWYUCYDcTGgTwMJkLc0X7rTgXo=
Endpoint = {public_ip}:51820
AllowedIPs = 0.0.0.0/0
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
