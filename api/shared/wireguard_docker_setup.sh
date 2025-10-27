#!/bin/bash
# WireGuard Direct Setup Script
# This script is executed during VM boot via cloud-init
# It sets up WireGuard directly on the host and saves the client configuration

set -e

# Configuration parameters
SERVER_PORT=51820
SERVER_NETWORK="10.13.13.0/24"
SERVER_ADDRESS="10.13.13.1"
CLIENT_ADDRESS="10.13.13.2"
DNS_SERVER="1.1.1.1"

# Install WireGuard tools
echo "Installing WireGuard tools..."
if command -v apt >/dev/null 2>&1; then
    # Ubuntu/Debian
    echo "Detected apt package manager"
    if apt update 2>/dev/null; then
        echo "Package list updated successfully"
        if apt install -y wireguard wireguard-tools 2>/dev/null; then
            echo "WireGuard tools installed successfully"
        else
            echo "ERROR: Failed to install wireguard-tools package"
            exit 1
        fi
    else
        echo "ERROR: Failed to update package list (may need sudo in test environment)"
        # For testing purposes, check if wg command already exists
        if command -v wg >/dev/null 2>&1; then
            echo "WireGuard tools already available, continuing..."
        else
            echo "ERROR: WireGuard tools not available and cannot install"
            exit 1
        fi
    fi
elif command -v tdnf >/dev/null 2>&1; then
    # CBL-Mariner - try installing from source as fallback
    echo "Installing WireGuard on CBL-Mariner..."
    cd /tmp
    curl -sL https://github.com/WireGuard/wireguard-tools/archive/refs/tags/v1.0.20210914.tar.gz | tar xz 2>/dev/null
    cd wireguard-tools-*
    if [ -f Makefile ]; then
        make && make install >/dev/null 2>&1
    else
        echo "Source installation failed, WireGuard tools not available"
        exit 1
    fi
else
    echo "ERROR: Unsupported package manager"
    exit 1
fi

# Check if wg command is available
if ! command -v wg >/dev/null 2>&1; then
    echo "ERROR: WireGuard tools not installed successfully"
    exit 1
fi

# Enable IP forwarding
echo "Enabling IP forwarding..."
echo 1 > /proc/sys/net/ipv4/ip_forward
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p >/dev/null 2>&1

# Get server's public IP - use ifconfig.me as primary method
echo "Getting server public IP..."

# Primary method: ifconfig.me (most reliable)
echo "Trying ifconfig.me..."
curl -s --max-time 10 ifconfig.me > /tmp/server_ip.txt 2>/dev/null
if [ -s /tmp/server_ip.txt ] && [[ "$(cat /tmp/server_ip.txt)" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SERVER_IP=$(cat /tmp/server_ip.txt | tr -d '\n' | tr -d '\r')
    echo "Got IP from ifconfig.me: $SERVER_IP"
else
    echo "ifconfig.me failed, trying Azure metadata..."
    # Fallback: Azure metadata service
    curl -s --max-time 10 -H Metadata:true "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" > /tmp/server_ip.txt 2>/dev/null
    if [ -s /tmp/server_ip.txt ] && [[ "$(cat /tmp/server_ip.txt)" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        SERVER_IP=$(cat /tmp/server_ip.txt | tr -d '\n' | tr -d '\r')
        echo "Got IP from Azure metadata: $SERVER_IP"
    else
        echo "Azure metadata failed, trying alternatives..."
        # Final fallback: alternative services
        for service in "https://api.ipify.org" "https://ipv4.icanhazip.com" "https://checkip.amazonaws.com"; do
            echo "Trying $service..."
            curl -s --max-time 5 "$service" > /tmp/server_ip.txt 2>/dev/null
            if [ -s /tmp/server_ip.txt ] && [[ "$(cat /tmp/server_ip.txt)" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                SERVER_IP=$(cat /tmp/server_ip.txt | tr -d '\n' | tr -d '\r')
                echo "Got IP from $service: $SERVER_IP"
                break
            fi
        done
    fi
fi

# Final fallback
if [ -z "$SERVER_IP" ]; then
    echo "Warning: Could not determine public IP, using placeholder"
    SERVER_IP="REPLACE_WITH_PUBLIC_IP"
fi

echo "Final SERVER_IP: '$SERVER_IP'"

# Generate keys directly using wg command
echo "Generating WireGuard keys..."
SERVER_PRIVATE_KEY=$(wg genkey)
SERVER_PUBLIC_KEY=$(echo "$SERVER_PRIVATE_KEY" | wg pubkey)

CLIENT_PRIVATE_KEY=$(wg genkey)
CLIENT_PUBLIC_KEY=$(echo "$CLIENT_PRIVATE_KEY" | wg pubkey)

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

# Save client configuration to file (for later retrieval via Run Command)
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

# Set proper permissions
chmod 600 /etc/wireguard/wg0.conf
chmod 644 /etc/wireguard/client.conf

# Start WireGuard interface
echo "Starting WireGuard interface..."
wg-quick up wg0

# Enable WireGuard to start on boot
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable wg-quick@wg0 >/dev/null 2>&1
    systemctl start wg-quick@wg0 >/dev/null 2>&1
fi

# Verify interface is up
if ! wg show wg0 >/dev/null 2>&1; then
    echo "ERROR: WireGuard interface failed to start"
    exit 1
fi

echo "WireGuard interface started successfully"
echo "Server IP: ${SERVER_IP}"
echo "Server Port: ${SERVER_PORT}"
echo "Setup complete!"
