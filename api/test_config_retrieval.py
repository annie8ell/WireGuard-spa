#!/usr/bin/env python3
"""
Test script to verify WireGuard config retrieval logic.
This simulates what the API does to retrieve configs from VMs.
"""
import os
import sys
import json
from pathlib import Path

# Add the shared module to path
sys.path.append(str(Path(__file__).parent))

from shared.vm_provisioner import get_vm_provisioner

def test_config_retrieval():
    """Test the config retrieval logic with our test VM."""
    print("Testing WireGuard config retrieval...")

    # Get the provisioner
    provisioner = get_vm_provisioner()

    # Test with our VM name
    vm_name = "wg-1761226066"

    print(f"Checking status for VM: {vm_name}")

    # Get VM status (this should retrieve the config via Run Command)
    success, error_msg, status_data = provisioner.get_vm_status(vm_name)

    if success:
        print("✅ Status check successful")
        print(f"Status: {status_data.get('status')}")
        print(f"Public IP: {status_data.get('publicIp')}")

        if 'confText' in status_data and status_data['confText']:
            print("✅ WireGuard config retrieved!")
            print("Config content:")
            print("=" * 50)
            print(status_data['confText'])
            print("=" * 50)
            return True
        else:
            print("❌ No config text in response")
            return False
    else:
        print(f"❌ Status check failed: {error_msg}")
        return False

if __name__ == "__main__":
    # Set environment to NOT dry run so it tries real Azure calls
    os.environ['DRY_RUN'] = 'false'

    success = test_config_retrieval()
    sys.exit(0 if success else 1)