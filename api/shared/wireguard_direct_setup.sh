#!/bin/bash
# Direct WireGuard Setup Script
# Installs and configures WireGuard directly on the host system
# Much simpler and faster than container-based approach

set -e

# Configuration parameters
SERVER_PORT=51820
SERVER_NETWORK="10.13.13.0/24"
SERVER_ADDRESS="10.13.13.1"
CLIENT_ADDRESS="10.13.13.2"
DNS_SERVER="1.1.1.1"

echo "=== Direct WireGuard Setup ==="
echo "Installing WireGuard tools..."

# Install WireGuard (works on both Ubuntu and CBL-Mariner)
if command -v apt >/dev/null 2>&1; then
    # Ubuntu/Debian
    apt update -y >/dev/null 2>&1
    apt install -y wireguard-tools iptables >/dev/null 2>&1
elif command -v tdnf >/dev/null 2>&1; then
    # CBL-Mariner
    tdnf update -y >/dev/null 2>&1
    tdnf install -y wireguard-tools iptables >/dev/null 2>&1
else
    echo "ERROR: Unsupported package manager"
    exit 1
fi

echo "Generating WireGuard keys..."
# Generate keys directly
SERVER_PRIVATE_KEY=$(wg genkey)
SERVER_PUBLIC_KEY=$(echo "$SERVER_PRIVATE_KEY" | wg pubkey)
CLIENT_PRIVATE_KEY=$(wg genkey)
CLIENT_PUBLIC_KEY=$(echo "$CLIENT_PRIVATE_KEY" | wg pubkey)

echo "Getting server public IP..."
# Get server's public IP (same logic as before)
curl -s --max-time 10 ifconfig.me > /tmp/server_ip.txt 2>/dev/null
if [ -s /tmp/server_ip.txt ] && [[ "$(cat /tmp/server_ip.txt)" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SERVER_IP=$(cat /tmp/server_ip.txt | tr -d '\n' | tr -d '\r')
    echo "Got IP from ifconfig.me: $SERVER_IP"
else
    # Fallback methods...
    SERVER_IP="REPLACE_WITH_PUBLIC_IP"
fi

echo "Final SERVER_IP: '$SERVER_IP'"

# Create WireGuard config directory
mkdir -p /etc/wireguard

# Create server configuration
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
PrivateKey = ${SERVER_PRIVATE_KEY}
Address = ${SERVER_ADDRESS}/24
ListenPort = ${SERVER_PORT}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
AllowedIPs = ${CLIENT_ADDRESS}/32
EOF

# Save client configuration
cat > /etc/wireguard/client.conf <<EOF
=== WIREGUARD_CLIENT_CONFIG_START ===
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}/24
DNS = ${DNS_SERVER}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${SERVER_IP}:${SERVER_PORT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
=== WIREGUARD_CLIENT_CONFIG_END ===
EOF

echo "Client config saved to /etc/wireguard/client.conf"

# Enable IP forwarding
echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

# Start WireGuard interface
echo "Starting WireGuard interface..."
wg-quick up wg0

# Enable auto-start on boot
echo "Enabling WireGuard service..."
systemctl enable wg-quick@wg0 >/dev/null 2>&1

# Verify it's running
if wg show wg0 >/dev/null 2>&1; then
    echo "WireGuard interface wg0 is active"
    wg show wg0
else
    echo "ERROR: WireGuard interface failed to start"
    exit 1
fi

echo "=== WireGuard Setup Complete ==="
echo "Server IP: ${SERVER_IP}"
echo "Server Port: ${SERVER_PORT}"
echo "Interface: wg0"
echo "Client config available at /etc/wireguard/client.conf"