# Implementation Notes - Docker-based WireGuard Deployment

## Why Ubuntu 22.04 LTS Instead of Flatcar?

**Problem:** Flatcar Container Linux VMs were getting stuck in 'Creating' state on Azure.

**Root Cause:** Ignition/cloud-init compatibility issues between Flatcar and Azure's provisioning system.

**Solution:** Switched to Ubuntu 22.04 LTS which has:
- Excellent cloud-init support
- Reliable Azure provisioning
- Built-in Docker compatibility
- Well-documented and widely supported

## Architecture Overview

### Setup Flow
1. **VM Creation** - Ubuntu 22.04 LTS VM provisioned with cloud-init config
2. **Boot-time Setup** - cloud-init runs `wireguard_docker_setup.sh`:
   - Installs Docker
   - Generates random WireGuard keys (using Docker containers with wireguard-tools)
   - Creates server config
   - Starts `linuxserver/wireguard` Docker container
   - Saves client config to `/etc/wireguard/client.conf`
3. **Config Retrieval** - When VM status is 'Succeeded', Run Command reads the saved config file
4. **IP Replacement** - API replaces placeholder IP with actual Azure public IP
5. **Delivery** - Client downloads wireguard.conf from frontend

### Why This Approach?

**Cloud-init for Setup:**
- Runs automatically during VM boot
- No waiting for VM to become accessible
- Setup happens in parallel with provisioning
- No external dependencies (SSH, etc.)

**Run Command for Retrieval:**
- Uses Azure VM Agent (built into Azure VMs)
- No SSH needed
- Fast and reliable
- Works immediately when VM is 'Succeeded'

## SSH Key Requirement

**Q:** Why do we need an SSH key if we're not using SSH?

**A:** Azure requires Linux VMs to have either:
- SSH public key, OR
- Admin password

This is an Azure platform requirement for VM authentication, not an application requirement.

**How It's Used:**
- `SSH_PUBLIC_KEY` environment variable (in Azure Static Web App settings)
- Provided to Azure during VM creation
- Satisfies Azure's authentication requirement
- **Application never uses it** - no SSH connections made

**Alternative:** Could use `AZURE_ADMIN_PASSWORD` instead, but SSH key is more secure.

## Key Storage

All credentials stored as **environment variables** in Azure Static Web App Application Settings:

Required:
- `SSH_PUBLIC_KEY` - For Azure VM provisioning requirement
- `AZURE_CLIENT_ID` - Service Principal for Azure SDK
- `AZURE_CLIENT_SECRET` - Service Principal secret
- `AZURE_TENANT_ID` - Azure AD tenant
- `AZURE_SUBSCRIPTION_ID` - Azure subscription
- `AZURE_RESOURCE_GROUP` - Where VMs are created

Optional:
- `AZURE_ADMIN_PASSWORD` - Alternative to SSH_PUBLIC_KEY
- `DRY_RUN` - Set to 'true' for testing without real VMs

## VM Deletion

The `delete_vm()` method removes:
- ✅ VM instance
- ✅ VM-specific Network Interface (NIC)
- ✅ VM-specific Public IP
- ❌ Shared VNet (preserved for reuse)
- ❌ Shared NSG (preserved for reuse)

This approach:
- Saves time on subsequent VM creations
- Reduces Azure API calls
- Maintains consistent network configuration
- Still allows complete cleanup by deleting the resource group

## Code Cleanup Done

Removed:
- `_setup_wireguard_via_ssh()` method - never called, dead code
- `paramiko` dependency - not needed
- `io` and `textwrap` imports - not used
- Test files: `api/test_config_retrieval.py`
- Ignition configs: `wireguard-ignition.json`, `wireguard-ignition.yaml`
- Unused cloud-init file: `api/shared/wireguard-cloud-init.yaml`

## Performance Characteristics

**VM Creation:** ~2-3 minutes
- Azure provisioning: ~60-90 seconds
- Cloud-init execution: ~60-90 seconds (Docker pull, container start)
- Total to 'Succeeded' state: ~2-3 minutes

**Config Retrieval:** ~5-10 seconds
- Run Command execution: ~3-5 seconds
- Network latency: ~1-2 seconds
- Parsing and IP replacement: <1 second

**Cost:** ~$0.0052/hour (Standard_B1ls in West Europe)
- With 30-minute sessions: ~$0.0026 per session
- Shared network resources: negligible added cost

## Future Improvements

1. **SSH Key Management:** Generate ephemeral keys per VM (current approach uses same key)
2. **Health Checks:** Add endpoint to verify WireGuard container is running
3. **Metrics:** Track setup success rate and timing
4. **Cleanup Job:** Automated deletion of VMs after 30 minutes (currently manual via tags)
5. **Multi-region:** Support VMs in different Azure regions based on user location

## Testing Checklist

- [x] DRY_RUN mode works
- [x] Real VM creation succeeds
- [x] Cloud-init executes successfully
- [x] WireGuard container starts
- [x] Config retrieval via Run Command works
- [x] IP replacement works correctly
- [x] Config downloads in frontend
- [x] VM deletion removes resources
- [ ] End-to-end VPN connectivity test (requires real client)
- [ ] 30-minute auto-deletion (requires timer/cleanup job)

## Known Limitations

1. **No Auto-Deletion:** VMs don't auto-delete after 30 minutes yet (requires separate cleanup job)
2. **Single VM Type:** Only Standard_B1ls supported (could add size selection)
3. **Single Region:** VMs created in resource group's region (could add region selection)
4. **No Health Monitoring:** No active monitoring of container health
5. **No Logs Access:** Can't easily view cloud-init or container logs (would need SSH or Log Analytics)

## Troubleshooting

**VM stuck in Creating:**
- Check resource group has capacity for B-series VMs
- Verify Service Principal has correct permissions
- Check Azure service health

**Config retrieval fails:**
- VM may still be running cloud-init (wait longer)
- Check Run Command is enabled (should be by default)
- Verify /etc/wireguard/client.conf exists on VM

**WireGuard container not starting:**
- Check cloud-init logs: `journalctl -u cloud-init`
- Verify Docker installed: `docker --version`
- Check container logs: `docker logs wireguard`

**IP placeholder not replaced:**
- Check Azure metadata service accessible from VM
- Verify public IP assigned to VM
- Check API logs for IP replacement logic
