#!/usr/bin/env python3
"""
REAL VM TEST: Create an actual Azure VM and test WireGuard setup.
This will create real Azure resources - use with caution!
"""
import sys
import os
import json
import time
import argparse

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

def load_credentials():
    """Load Azure credentials from local.settings.json."""
    settings_file = 'api/local.settings.json'
    if not os.path.exists(settings_file):
        print(f"❌ Settings file not found: {settings_file}")
        return False

    with open(settings_file, 'r') as f:
        settings = json.load(f)

    # Set environment variables
    values = settings.get('Values', {})
    required_vars = [
        'AZURE_SUBSCRIPTION_ID',
        'AZURE_RESOURCE_GROUP',
        'AZURE_CLIENT_ID',
        'AZURE_CLIENT_SECRET',
        'AZURE_TENANT_ID',
        'SSH_PUBLIC_KEY'
    ]

    for var in required_vars:
        if var not in values:
            print(f"❌ Missing required setting: {var}")
            return False
        os.environ[var] = values[var]

    # Ensure we're NOT in dry run mode
    os.environ['DRY_RUN'] = 'false'

    print("✅ Azure credentials loaded")
    return True

def create_test_vm():
    """Create a real test VM and monitor its progress."""
    print("🚀 Creating REAL test VM with WireGuard setup...")

    try:
        from api.shared.vm_provisioner import get_vm_provisioner

        provisioner = get_vm_provisioner()
        print("✅ VM Provisioner initialized")

        # Create VM
        print("📡 Starting VM creation...")
        success, error, result = provisioner.get_or_create_vm(location='westeurope')

        if not success:
            print(f"❌ VM creation failed: {error}")
            return None

        vm_name = result['vmName']
        operation_id = result['operationId']
        print(f"✅ VM creation initiated: {vm_name}")
        print(f"   Operation ID: {operation_id}")
        print(f"   Status: {result['status']}")

        return vm_name

    except Exception as e:
        print(f"❌ Error creating VM: {e}")
        import traceback
        traceback.print_exc()
        return None

def monitor_vm_status(vm_name, max_wait_minutes=10):
    """Monitor VM creation and WireGuard setup progress."""
    print(f"📊 Monitoring VM: {vm_name}")

    try:
        from api.shared.vm_provisioner import get_vm_provisioner

        provisioner = get_vm_provisioner()
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60

        while time.time() - start_time < max_wait_seconds:
            success, error, status_result = provisioner.get_vm_status(vm_name)

            if not success:
                print(f"❌ Status check failed: {error}")
                return False

            status = status_result['status']
            elapsed = int(time.time() - start_time)

            if status == 'Succeeded':
                public_ip = status_result.get('publicIp')
                conf_text = status_result.get('confText')

                print(f"✅ VM ready after {elapsed}s!")
                print(f"   Public IP: {public_ip}")
                print(f"   Config length: {len(conf_text) if conf_text else 0} characters")

                if conf_text:
                    print("✅ WireGuard config retrieved successfully!")
                    # Show first few lines of config
                    lines = conf_text.split('\n')[:10]
                    print("   Config preview:")
                    for line in lines:
                        print(f"     {line}")
                    return True
                else:
                    print("❌ No WireGuard config retrieved - debugging VM...")
                    debug_output = debug_vm(vm_name)
                    if debug_output:
                        print("   Debug output from VM:")
                        print(f"   {debug_output}")
                    return False

            elif status == 'Failed':
                error_msg = status_result.get('error', 'Unknown error')
                print(f"❌ VM failed: {error_msg}")
                # Still try to debug
                debug_output = debug_vm(vm_name)
                if debug_output:
                    print("   Debug output from failed VM:")
                    print(f"   {debug_output}")
                return False

            elif status in ['Creating', 'InProgress']:
                progress = status_result.get('progress', '')
                print(f"⏳ {status} ({elapsed}s) - {progress}")
                time.sleep(10)  # Wait 10 seconds before next check

            else:
                print(f"ℹ️  Status: {status} ({elapsed}s)")
                time.sleep(5)

        print(f"⏰ Timeout after {max_wait_minutes} minutes")
        return False

    except Exception as e:
        print(f"❌ Error monitoring VM: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_vm(vm_name):
    """Debug VM by running simple commands to see what's there."""
    try:
        from api.shared.vm_provisioner import get_vm_provisioner
        provisioner = get_vm_provisioner()

        # Try to see if the setup script exists and what happened
        debug_script = """
#!/bin/bash
echo "=== DEBUG INFO ==="
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
echo "Date: $(date)"
echo ""
echo "=== WIREGUARD DIRECT SETUP SCRIPT ==="
if [ -f /usr/local/bin/wireguard_direct_setup.sh ]; then
    echo "Setup script exists:"
    ls -la /usr/local/bin/wireguard_direct_setup.sh
    echo "First 10 lines of script:"
    head -10 /usr/local/bin/wireguard_direct_setup.sh
else
    echo "Setup script NOT found!"
fi
echo ""
echo "=== WIREGUARD DIRECTORY ==="
if [ -d /etc/wireguard ]; then
    echo "WireGuard directory exists:"
    ls -la /etc/wireguard/
    if [ -f /etc/wireguard/client.conf ]; then
        echo "Client config exists - first 10 lines:"
        head -10 /etc/wireguard/client.conf
    else
        echo "Client config NOT found!"
    fi
else
    echo "WireGuard directory NOT found!"
fi
echo ""
echo "=== SYSTEMD STATUS ==="
systemctl status wg-quick@wg0 2>/dev/null || echo "wg-quick service not running"
echo ""
echo "=== CLOUD-INIT LOG ==="
if [ -f /var/log/cloud-init-output.log ]; then
    echo "Last 20 lines of cloud-init log:"
    tail -20 /var/log/cloud-init-output.log
else
    echo "No cloud-init log found"
fi
echo ""
echo "=== PACKAGES ==="
dpkg -l | grep -i wireguard || echo "No wireguard packages found"
echo "=== END DEBUG ==="
"""

        run_command_params = {
            'command_id': 'RunShellScript',
            'script': debug_script.split('\n')
        }

        print("   Running debug command on VM...")
        poller = provisioner.compute_client.virtual_machines.begin_run_command(
            provisioner.resource_group,
            vm_name,
            run_command_params
        )

        result = poller.result(timeout=30)
        if result.value and len(result.value) > 0:
            return result.value[0].message
        return "No debug output received"

    except Exception as e:
        return f"Debug command failed: {e}"

def cleanup_test_vm(vm_name):
    """Clean up the test VM and associated resources."""
    print(f"🧹 Cleaning up test VM: {vm_name}")

    try:
        from api.shared.vm_provisioner import get_vm_provisioner

        provisioner = get_vm_provisioner()
        success, error = provisioner.delete_vm(vm_name)

        if success:
            print("✅ Test VM and resources deleted successfully")
            return True
        else:
            print(f"❌ Failed to delete VM: {error}")
            return False

    except Exception as e:
        print(f"❌ Error deleting VM: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='Test real VM creation with WireGuard')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip VM cleanup after test (for debugging)')
    parser.add_argument('--max-wait', type=int, default=10,
                       help='Maximum wait time in minutes (default: 10)')
    parser.add_argument('--auto-confirm', action='store_true',
                       help='Skip confirmation prompt (use with caution)')

    args = parser.parse_args()

    print("🧪 REAL VM TEST: WireGuard Setup Validation")
    print("=" * 60)
    print("⚠️  WARNING: This will create REAL Azure resources!")
    print("   - VM: Standard_B1ls (costs ~$10-15/month if not cleaned up)")
    print("   - Public IP: Dynamic (small cost)")
    print("   - Network resources: Shared (minimal cost)")
    print("=" * 60)

    # Auto-confirm if flag is set, otherwise prompt
    if not args.auto_confirm:
        print("Prompting for confirmation...")
        try:
            response = input("Are you sure you want to continue? (type 'yes'): ")
            if response.lower() != 'yes':
                print("Test cancelled.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\nTest cancelled.")
            return 0
    else:
        print("Auto-confirm enabled - proceeding without prompt")

    # Load credentials
    if not load_credentials():
        return 1

    # Create test VM
    vm_name = create_test_vm()
    if not vm_name:
        return 1

    # Monitor progress
    success = monitor_vm_status(vm_name, args.max_wait)

    # Cleanup
    if not args.no_cleanup:
        print("\n" + "=" * 60)
        cleanup_success = cleanup_test_vm(vm_name)
    else:
        print(f"\n⚠️  VM {vm_name} NOT cleaned up (use --no-cleanup for debugging)")
        print("   Remember to manually delete when done testing!")
        cleanup_success = True

    print("\n" + "=" * 60)
    if success:
        print("🎉 TEST PASSED: WireGuard setup works on real VM!")
        print("   Ready for deployment.")
        return 0
    else:
        print("❌ TEST FAILED: WireGuard setup did not work.")
        print("   Fix issues before deploying.")
        return 1

if __name__ == '__main__':
    sys.exit(main())