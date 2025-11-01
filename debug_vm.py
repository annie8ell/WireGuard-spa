#!/usr/bin/env python3
"""
Simple debug test: Create VM and immediately debug what's on it.
"""
import sys
import os
import json

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

def debug_vm_immediately(vm_name):
    """Debug VM immediately after creation."""
    try:
        from api.shared.vm_provisioner import get_vm_provisioner
        provisioner = get_vm_provisioner()

        # Simple debug script
        debug_script = """
#!/bin/bash
echo "=== IMMEDIATE DEBUG ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo "Current user: $(whoami)"
echo "Working directory: $(pwd)"
echo ""
echo "=== PROCESSES ==="
ps aux | head -10
echo ""
echo "=== DISK USAGE ==="
df -h
echo ""
echo "=== NETWORK ==="
ip addr show | head -20
echo ""
echo "=== SERVICES ==="
systemctl list-units --type=service --state=running | head -10
echo "=== END DEBUG ==="
"""

        run_command_params = {
            'command_id': 'RunShellScript',
            'script': debug_script.split('\n')
        }

        print("🔍 Running debug command on VM...")
        poller = provisioner.compute_client.virtual_machines.begin_run_command(
            provisioner.resource_group,
            vm_name,
            run_command_params
        )

        result = poller.result(timeout=30)
        if result.value and len(result.value) > 0:
            print("📄 Debug output:")
            print(result.value[0].message)
            return True
        else:
            print("❌ No debug output received")
            return False

    except Exception as e:
        print(f"❌ Debug command failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_and_debug_vm():
    """Create VM and immediately debug it."""
    print("🚀 Creating test VM for debugging...")

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
        print(f"✅ VM creation initiated: {vm_name}")

        # Wait a bit for VM to be ready
        print("⏳ Waiting 60 seconds for VM to initialize...")
        import time
        time.sleep(60)

        # Debug immediately
        debug_success = debug_vm_immediately(vm_name)

        return vm_name, debug_success

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, False

def main():
    """Main function."""
    print("🔧 VM DEBUG TEST")
    print("=" * 40)

    # Load credentials
    if not load_credentials():
        return 1

    # Create and debug VM
    result = create_and_debug_vm()

    if result:
        vm_name, debug_success = result
        print(f"\n✅ VM created: {vm_name}")
        if debug_success:
            print("✅ Debug successful")
        else:
            print("❌ Debug failed")

        # Ask if user wants to keep VM for manual inspection
        try:
            keep = input(f"\nKeep VM {vm_name} for manual inspection? (y/N): ")
            if keep.lower() == 'y':
                print(f"⚠️  VM {vm_name} NOT deleted - remember to clean it up manually!")
                return 0
        except:
            pass

        # Cleanup
        print(f"🧹 Cleaning up VM {vm_name}...")
        from api.shared.vm_provisioner import get_vm_provisioner
        provisioner = get_vm_provisioner()
        provisioner.delete_vm(vm_name)
        print("✅ Cleanup complete")

    return 0

if __name__ == '__main__':
    sys.exit(main())