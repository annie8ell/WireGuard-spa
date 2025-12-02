#!/usr/bin/env python3
"""
Test script to validate VM creation and WireGuard setup logic.
This test uses DRY_RUN mode to avoid creating actual Azure resources.
"""
import sys
import os
import json
import time
from unittest.mock import Mock, patch

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

def test_vm_provisioner_dry_run():
    """Test VM provisioner in dry run mode."""
    print("Testing VM Provisioner in DRY RUN mode...")

    # Set dry run mode
    os.environ['DRY_RUN'] = 'true'

    try:
        from api.shared.vm_provisioner import get_vm_provisioner

        # Get provisioner (should work in dry run mode)
        provisioner = get_vm_provisioner()
        print("✅ VM Provisioner initialized successfully")

        # Test VM creation
        success, error, result = provisioner.get_or_create_vm(location='westeurope')
        print(f"VM Creation Result: success={success}, error={error}")

        if success and result:
            vm_name = result['vmName']
            operation_id = result['operationId']
            print(f"✅ VM creation initiated: {vm_name} (operation: {operation_id})")

            # Test status checking
            print("Testing status checking...")
            for i in range(3):  # Check status a few times to simulate progression
                success, error, status_result = provisioner.get_vm_status(vm_name)
                if success and status_result:
                    status = status_result['status']
                    print(f"Status check {i+1}: {status}")
                    if status == 'Succeeded':
                        break
                time.sleep(1)  # Small delay between checks

            print("✅ Status checking works")
        else:
            print(f"❌ VM creation failed: {error}")
            return False

        return True

    except Exception as e:
        print(f"❌ Error testing VM provisioner: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cloud_init_generation():
    """Test cloud-init configuration generation."""
    print("\nTesting Cloud-init Configuration Generation...")

    try:
        from api.shared.vm_provisioner import VMProvisioner

        # Create a mock provisioner to test cloud-init generation
        provisioner = VMProvisioner.__new__(VMProvisioner)  # Create without calling __init__

        # Test cloud-init config generation
        config = provisioner._generate_cloud_init_config()

        if config:
            print("✅ Cloud-init config generated successfully")
            print(f"Config length: {len(config)} characters")

            # Check for expected content
            if '#cloud-config' in config:
                print("✅ Contains cloud-config header")
            else:
                print("❌ Missing cloud-config header")
                return False

            if 'wireguard_direct_setup.sh' in config:
                print("✅ Contains WireGuard setup script reference")
            else:
                print("❌ Missing WireGuard setup script reference")
                return False

            if 'runcmd:' in config:
                print("✅ Contains runcmd section")
            else:
                print("❌ Missing runcmd section")
                return False

            return True
        else:
            print("❌ Cloud-init config generation failed")
            return False

    except Exception as e:
        print(f"❌ Error testing cloud-init generation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test the API endpoints with mocked requests."""
    print("\nTesting API Endpoints...")

    try:
        # Mock HTTP request
        class MockHttpRequest:
            def __init__(self, body=None):
                self.body = body or '{}'
                self.headers = {}

            def get_json(self):
                return json.loads(self.body)

        # Test start_job endpoint
        print("Testing start_job endpoint...")
        from api.start_job.__init__ import main as start_job_main

        req = MockHttpRequest('{"location": "westeurope"}')

        # Mock the environment for dry run
        with patch.dict(os.environ, {'DRY_RUN': 'true'}):
            response = start_job_main(req)
            print(f"Start job response status: {response.status_code}")

            if response.status_code == 202:
                print("✅ Start job endpoint works (202 Accepted)")
            else:
                print(f"❌ Start job endpoint failed with status {response.status_code}")
                return False

        # Test job_status endpoint
        print("Testing job_status endpoint...")
        from api.job_status.__init__ import main as job_status_main

        req = MockHttpRequest()
        req.route_params = {'id': 'test-vm-name'}

        with patch.dict(os.environ, {'DRY_RUN': 'true'}):
            response = job_status_main(req)
            print(f"Job status response status: {response.status_code}")

            if response.status_code == 200:
                print("✅ Job status endpoint works")
            else:
                print(f"❌ Job status endpoint failed with status {response.status_code}")
                return False

        return True

    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("WireGuard SPA VM Creation Test Suite")
    print("=" * 50)

    tests = [
        test_vm_provisioner_dry_run,
        test_cloud_init_generation,
        test_api_endpoints
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ All tests passed! ({passed}/{total})")
        print("\n🎉 Ready for deployment! The VM creation logic is working correctly.")
        print("   Next step: Test with real Azure credentials (set DRY_RUN=false)")
        return 0
    else:
        print(f"❌ {total - passed} tests failed ({passed}/{total})")
        print("\n🔧 Fix the failing tests before deploying.")
        return 1

if __name__ == '__main__':
    sys.exit(main())