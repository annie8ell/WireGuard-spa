"""Azure VM management for WireGuard."""
import logging
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from .config import get_azure_subscription_id, get_azure_resource_group, is_dry_run

logger = logging.getLogger(__name__)

class VMManager:
    """Manages Azure VM lifecycle for WireGuard."""
    
    def __init__(self):
        self.subscription_id = get_azure_subscription_id()
        self.resource_group = get_azure_resource_group()
        self.credential = DefaultAzureCredential()
        
        if not is_dry_run():
            self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
            self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
            self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
    
    def create_vm(self, vm_name, location='eastus'):
        """Create a new VM for WireGuard."""
        if is_dry_run():
            logger.info(f"DRY RUN: Would create VM {vm_name} in {location}")
            return {
                'vm_name': vm_name,
                'public_ip': '1.2.3.4',
                'status': 'dry_run'
            }
        
        logger.info(f"Creating VM {vm_name} in {location}")
        
        # Create network interface
        nic_name = f"{vm_name}-nic"
        public_ip_name = f"{vm_name}-ip"
        vnet_name = f"{vm_name}-vnet"
        subnet_name = f"{vm_name}-subnet"
        
        # Create VNet and Subnet
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
        
        vnet_result = self.network_client.virtual_networks.begin_create_or_update(
            self.resource_group,
            vnet_name,
            vnet_params
        ).result()
        
        # Create Public IP
        public_ip_params = {
            'location': location,
            'sku': {'name': 'Standard'},
            'public_ip_allocation_method': 'Static'
        }
        
        public_ip_result = self.network_client.public_ip_addresses.begin_create_or_update(
            self.resource_group,
            public_ip_name,
            public_ip_params
        ).result()
        
        # Create NIC
        nic_params = {
            'location': location,
            'ip_configurations': [{
                'name': 'ipconfig1',
                'subnet': {'id': vnet_result.subnets[0].id},
                'public_ip_address': {'id': public_ip_result.id}
            }]
        }
        
        nic_result = self.network_client.network_interfaces.begin_create_or_update(
            self.resource_group,
            nic_name,
            nic_params
        ).result()
        
        # Create VM
        vm_params = {
            'location': location,
            'hardware_profile': {
                'vm_size': 'Standard_B1s'
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
                'admin_username': 'azureuser',
                'admin_password': 'P@ssw0rd1234!',
                'linux_configuration': {
                    'disable_password_authentication': False
                }
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': nic_result.id,
                    'properties': {
                        'primary': True
                    }
                }]
            }
        }
        
        vm_result = self.compute_client.virtual_machines.begin_create_or_update(
            self.resource_group,
            vm_name,
            vm_params
        ).result()
        
        logger.info(f"VM {vm_name} created successfully")
        
        return {
            'vm_name': vm_name,
            'public_ip': public_ip_result.ip_address,
            'status': 'running'
        }
    
    def destroy_vm(self, vm_name):
        """Destroy a VM and associated resources."""
        if is_dry_run():
            logger.info(f"DRY RUN: Would destroy VM {vm_name}")
            return {'status': 'destroyed', 'dry_run': True}
        
        logger.info(f"Destroying VM {vm_name}")
        
        # Delete VM
        self.compute_client.virtual_machines.begin_delete(
            self.resource_group,
            vm_name
        ).wait()
        
        # Delete NIC
        nic_name = f"{vm_name}-nic"
        self.network_client.network_interfaces.begin_delete(
            self.resource_group,
            nic_name
        ).wait()
        
        # Delete Public IP
        public_ip_name = f"{vm_name}-ip"
        self.network_client.public_ip_addresses.begin_delete(
            self.resource_group,
            public_ip_name
        ).wait()
        
        # Delete VNet
        vnet_name = f"{vm_name}-vnet"
        self.network_client.virtual_networks.begin_delete(
            self.resource_group,
            vnet_name
        ).wait()
        
        logger.info(f"VM {vm_name} destroyed successfully")
        
        return {'status': 'destroyed'}
    
    def get_vm_status(self, vm_name):
        """Get status of a VM."""
        if is_dry_run():
            return {'status': 'unknown', 'dry_run': True}
        
        try:
            vm = self.compute_client.virtual_machines.get(
                self.resource_group,
                vm_name,
                expand='instanceView'
            )
            
            statuses = vm.instance_view.statuses if vm.instance_view else []
            power_state = 'unknown'
            
            for status in statuses:
                if status.code.startswith('PowerState/'):
                    power_state = status.code.split('/')[-1]
            
            return {
                'vm_name': vm_name,
                'status': power_state,
                'location': vm.location
            }
        except Exception as e:
            logger.error(f"Error getting VM status: {str(e)}")
            return {'status': 'not_found', 'error': str(e)}
