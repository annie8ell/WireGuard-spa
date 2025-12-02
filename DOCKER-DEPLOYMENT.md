# Docker-Based WireGuard Deployment

This document describes the implementation of Docker-based WireGuard deployment for the WireGuard On-Demand Launcher, as specified in issues #32 and #33.

## Overview

The system uses **Ubuntu 22.04 LTS** to provision WireGuard VPN servers in Docker containers. Ubuntu was chosen over Flatcar Container Linux due to better Azure cloud-init compatibility and reliable VM provisioning. This provides stateless key generation and full automation with Docker containerization.

## Architecture

### VM Provisioning Flow

```
1. User requests VPN via frontend
   ↓
2. API creates Ubuntu 22.04 LTS VM (Standard_B1ls)
   - Publisher: Canonical
   - Offer: 0001-com-ubuntu-server-jammy
   - SKU: 22_04-lts-gen2
   - Custom Data: cloud-init config with WireGuard setup script
   ↓
3. VM boots and cloud-init runs wireguard_docker_setup.sh:
   - Installs Docker (via cloud-init packages)
   - Generates random WireGuard keys using Docker containers
   - Creates server configuration
   - Pulls linuxserver/wireguard Docker image
   - Starts WireGuard container with proper networking
   - Saves client configuration to /etc/wireguard/client.conf
   ↓
4. When VM status = 'Succeeded', API uses Run Command to retrieve config
   ↓
5. Run Command reads /etc/wireguard/client.conf
   ↓
6. API extracts client config and replaces IP placeholder with actual public IP
   ↓
7. Frontend receives config and displays download button
   ↓
8. User downloads wireguard.conf and connects
```

## Key Components

### 1. VM Provisioner (`api/shared/vm_provisioner.py`)

**Changes:**
- Updated `create_vm()` to use Ubuntu 22.04 LTS image
- Modified `get_vm_status()` to use Run Command to retrieve generated config
- Added `_generate_cloud_init_config()` to embed setup script in VM custom_data
- Added `_retrieve_wireguard_config_via_run_command()` to read config file
- Added `_extract_wireguard_config()` to parse Run Command output
- Added IP placeholder replacement logic to ensure correct endpoint

**Image Configuration:**
```python
'image_reference': {
    'publisher': 'Canonical',
    'offer': '0001-com-ubuntu-server-jammy',
    'sku': '22_04-lts-gen2',
    'version': 'latest'
}
```

### 2. SSH Key Requirement

**Note:** Azure requires Linux VMs to have either SSH public key or admin password for authentication. The implementation uses `SSH_PUBLIC_KEY` environment variable (stored in Azure Static Web App settings) to satisfy this requirement.

**Important:** The SSH key is ONLY used for Azure's VM provisioning requirement. The actual WireGuard setup and config retrieval use:
- **Cloud-init** for setup during VM boot
- **Azure Run Command** (via VM Agent) for config retrieval

No SSH connections are made by the application code - all automation happens through Azure's native mechanisms.

### 3. WireGuard Setup Script (`api/shared/wireguard_docker_setup.sh`)

**Purpose:** Embedded in VM's cloud-init custom_data and executed during first boot.

**Key Steps:**
1. Get server's public IP from Azure metadata service
2. Generate WireGuard keys using temporary Docker containers with wireguard-tools
3. Create server configuration at `/etc/wireguard/wg0.conf`
4. Pull `linuxserver/wireguard` Docker image
5. Start WireGuard container with:
   - Network capabilities (NET_ADMIN, SYS_MODULE)
   - UDP port 51820 exposed
   - Config volume mounted
   - Kernel modules mounted
6. Output client configuration between markers

**Key Generation:**
```bash
# Server keys
PRIVATE_KEY=$(docker run --rm alpine:latest sh -c "apk add --no-cache wireguard-tools && wg genkey")
PUBLIC_KEY=$(docker run --rm alpine:latest sh -c "apk add --no-cache wireguard-tools && echo '$PRIVATE_KEY' | wg pubkey")

# Client keys (same approach)
```

**Container Configuration:**
```bash
docker run -d \
  --name=wireguard \
  --cap-add=NET_ADMIN \
  --cap-add=SYS_MODULE \
  --sysctl="net.ipv4.conf.all.src_valid_mark=1" \
  -p 51820:51820/udp \
  -v /etc/wireguard:/config \
  -v /lib/modules:/lib/modules:ro \
  --restart unless-stopped \
  linuxserver/wireguard
```

### 3. Client Configuration Output

The script outputs the client configuration between markers for easy extraction:

```
=== WIREGUARD_CLIENT_CONFIG_START ===
[Interface]
PrivateKey = <generated_client_private_key>
Address = 10.13.13.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = <generated_server_public_key>
Endpoint = <vm_public_ip>:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
=== WIREGUARD_CLIENT_CONFIG_END ===
```

The API extracts this section and returns it to the frontend.

## Benefits

### 1. Faster Boot Times
- Flatcar Container Linux is optimized for containers
- Minimal OS footprint reduces boot time
- Docker pre-installed, no package installation needed

### 2. Stateless Key Generation
- Keys generated on-VM, not stored in API
- Each VM gets unique random keys
- No key management in the control plane

### 3. Container Isolation
- WireGuard runs in isolated Docker container
- Easy to update by pulling new container image
- Proven `linuxserver/wireguard` container image

### 4. Full Automation
- No manual steps required
- Complete automation from VM creation to config delivery
- Run Command handles all setup

### 5. Security
- Keys never leave the VM
- No persistent storage of secrets
- Ephemeral VMs with 30-minute lifetime

## Network Configuration

### Network Security Group Rules

The VM's NSG includes rules for:
- **UDP 51820**: WireGuard VPN traffic (priority 100)
- **TCP 22**: SSH access for debugging (priority 110)

### WireGuard Network

- **Server Network**: 10.13.13.0/24
- **Server Address**: 10.13.13.1/24
- **Client Address**: 10.13.13.2/24
- **DNS Server**: 1.1.1.1 (Cloudflare)
- **Allowed IPs**: 0.0.0.0/0, ::/0 (full tunnel)

### iptables NAT Configuration

The server configuration includes PostUp/PostDown rules for NAT:

```
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
```

## Error Handling

### Run Command Failures

If Run Command fails or times out:
1. API logs the error
2. Falls back to sample configuration (for testing)
3. Returns status to frontend
4. User can retry

### VM Provisioning Failures

If VM creation fails:
1. Azure returns error status
2. API propagates error to frontend
3. Frontend displays error message
4. User can retry

## Testing

### DRY_RUN Mode

When `DRY_RUN=true` environment variable is set:
- No actual VMs are created
- Simulates realistic timing (Creating → Running → Succeeded)
- Returns sample configuration
- Useful for testing without Azure costs

### Test Results

All tests pass in DRY_RUN mode:
- ✅ VM provisioning simulation
- ✅ Status polling with progression
- ✅ Config extraction logic
- ✅ API endpoint integration
- ✅ Frontend compatibility

## Production Considerations

### Before Deploying to Production

1. **Test with Real Azure Resources**
   - Set `DRY_RUN=false`
   - Verify VM creation works
   - Test Run Command execution
   - Verify WireGuard connectivity

2. **SSH Key Management**
   - Currently uses placeholder SSH key
   - Consider using Azure Key Vault for key management
   - Or generate ephemeral SSH keys per VM

3. **Monitoring**
   - Set up Application Insights
   - Monitor Run Command execution time
   - Track VM provisioning success rate
   - Alert on failures

4. **Cost Management**
   - Monitor VM usage
   - Verify 30-minute auto-deletion works
   - Consider implementing usage quotas per user

5. **Security Hardening**
   - Review NSG rules
   - Consider restricting SSH access
   - Implement rate limiting
   - Add audit logging

## Troubleshooting

### VM Takes Too Long to Provision

- Check Azure region performance
- Verify Flatcar image is available in region
- Consider using different VM size

### Run Command Times Out

- Default timeout is 300 seconds (5 minutes)
- Check VM has internet access for Docker pulls
- Verify Azure metadata service is accessible
- Check Docker container logs if SSH access available

### WireGuard Config Not Extracted

- Verify markers are present in script output
- Check Run Command output in logs
- Ensure script has execute permissions
- Verify bash syntax is correct

### Container Fails to Start

- Check Docker is running on VM
- Verify kernel modules are loaded
- Check for conflicting containers
- Review Docker logs via SSH

## Future Enhancements

### Potential Improvements

1. **Caching Docker Images**
   - Pre-pull WireGuard image to reduce setup time
   - Store in Azure Container Registry

2. **Multiple Clients per VM**
   - Support multiple concurrent clients
   - Dynamic peer configuration

3. **Custom DNS Configuration**
   - Allow users to specify DNS servers
   - Support split-tunnel configurations

4. **QR Code Generation**
   - Generate QR codes for mobile clients
   - Embed in frontend response

5. **Performance Monitoring**
   - Track WireGuard metrics
   - Report bandwidth usage
   - Connection quality indicators

## References

- [Flatcar Container Linux Documentation](https://www.flatcar.org/)
- [linuxserver/wireguard Docker Image](https://github.com/linuxserver/docker-wireguard)
- [Azure Run Command Documentation](https://docs.microsoft.com/en-us/azure/virtual-machines/run-command-overview)
- [WireGuard Documentation](https://www.wireguard.com/)

## Related Issues

- Issue #32: Switch to Docker-based WireGuard deployment
- Issue #33: Implement Run Command to generate and fetch client config
