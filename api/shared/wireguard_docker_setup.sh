#!/bin/bash
# WireGuard Docker Setup Script
# This script is executed during VM boot via cloud-init
# It sets up WireGuard in a Docker container and saves the client configuration

set -e

# Configuration parameters
SERVER_PORT=51820
SERVER_NETWORK="10.13.13.0/24"
SERVER_ADDRESS="10.13.13.1"
CLIENT_ADDRESS="10.13.13.2"
DNS_SERVER="1.1.1.1"

# Get server's public IP using Azure metadata service
echo "Getting server public IP..."
SERVER_IP=$(curl -s -H Metadata:true "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" 2>/dev/null || echo "UNKNOWN")

if [ "$SERVER_IP" = "UNKNOWN" ]; then
    echo "Warning: Could not get public IP from Azure metadata, trying alternative method"
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "UNKNOWN")
fi

# Generate keys using a temporary container with wireguard-tools
echo "Generating WireGuard keys..."
PRIVATE_KEY=$(docker run --rm alpine:latest sh -c "apk add --no-cache wireguard-tools >/dev/null 2>&1 && wg genkey" 2>/dev/null)
PUBLIC_KEY=$(docker run --rm alpine:latest sh -c "apk add --no-cache wireguard-tools >/dev/null 2>&1 && echo '$PRIVATE_KEY' | wg pubkey" 2>/dev/null)

CLIENT_PRIVATE_KEY=$(docker run --rm alpine:latest sh -c "apk add --no-cache wireguard-tools >/dev/null 2>&1 && wg genkey" 2>/dev/null)
CLIENT_PUBLIC_KEY=$(docker run --rm alpine:latest sh -c "apk add --no-cache wireguard-tools >/dev/null 2>&1 && echo '$CLIENT_PRIVATE_KEY' | wg pubkey" 2>/dev/null)

# Create WireGuard config directory on host
mkdir -p /etc/wireguard

# Create server configuration
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
PrivateKey = ${PRIVATE_KEY}
Address = ${SERVER_ADDRESS}/24
ListenPort = ${SERVER_PORT}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
AllowedIPs = ${CLIENT_ADDRESS}/32
EOF

# Save client configuration to file (for later retrieval via Run Command)
cat > /etc/wireguard/client.conf <<EOF
=== WIREGUARD_CLIENT_CONFIG_START ===
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}/24
DNS = ${DNS_SERVER}

[Peer]
PublicKey = ${PUBLIC_KEY}
Endpoint = ${SERVER_IP}:${SERVER_PORT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
=== WIREGUARD_CLIENT_CONFIG_END ===
EOF

echo "Client config saved to /etc/wireguard/client.conf"

echo "Pulling WireGuard Docker image..."
docker pull linuxserver/wireguard:latest >/dev/null 2>&1

# Stop and remove any existing container
docker stop wireguard 2>/dev/null || true
docker rm wireguard 2>/dev/null || true

echo "Starting WireGuard container..."
# Start WireGuard container
docker run -d \
  --name=wireguard \
  --cap-add=NET_ADMIN \
  --cap-add=SYS_MODULE \
  --sysctl="net.ipv4.conf.all.src_valid_mark=1" \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Etc/UTC \
  -p ${SERVER_PORT}:${SERVER_PORT}/udp \
  -v /etc/wireguard:/config \
  -v /lib/modules:/lib/modules:ro \
  --restart unless-stopped \
  linuxserver/wireguard >/dev/null 2>&1

# Wait for container to be ready
sleep 10

# Verify container is running
if ! docker ps | grep -q wireguard; then
    echo "ERROR: WireGuard container failed to start"
    docker logs wireguard 2>&1 || true
    exit 1
fi

echo "WireGuard container started successfully"
echo "Server IP: ${SERVER_IP}"
echo "Server Port: ${SERVER_PORT}"
echo "Setup complete!"
