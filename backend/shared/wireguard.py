"""
WireGuard configuration generation utilities.
"""
import os
import secrets
import base64
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization


def generate_keypair() -> tuple[str, str]:
    """
    Generate a WireGuard keypair.
    
    Returns:
        tuple: (private_key_base64, public_key_base64)
    """
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    private_key_b64 = base64.b64encode(private_key_bytes).decode('utf-8')
    public_key_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
    
    return private_key_b64, public_key_b64


def generate_sample_config(server_ip: str = "203.0.113.10") -> str:
    """
    Generate a sample WireGuard client configuration for DRY_RUN mode.
    
    Args:
        server_ip: Public IP address of the WireGuard server (sample for DRY_RUN)
    
    Returns:
        str: WireGuard client configuration text
    """
    # Generate client keypair
    client_private, client_public = generate_keypair()
    
    # Generate server keypair (in real mode, this comes from the actual server)
    server_private, server_public = generate_keypair()
    
    config = f"""[Interface]
PrivateKey = {client_private}
Address = 10.8.0.2/24
DNS = 1.1.1.1

[Peer]
PublicKey = {server_public}
Endpoint = {server_ip}:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
    
    return config


def generate_client_config(server_public_key: str, server_ip: str, 
                          client_address: str = "10.8.0.2/24") -> tuple[str, str, str]:
    """
    Generate a WireGuard client configuration.
    
    Args:
        server_public_key: Server's public key
        server_ip: Server's public IP address
        client_address: Client's VPN IP address with CIDR notation
    
    Returns:
        tuple: (config_text, client_private_key, client_public_key)
    """
    # Generate client keypair
    client_private, client_public = generate_keypair()
    
    config = f"""[Interface]
PrivateKey = {client_private}
Address = {client_address}
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_ip}:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""
    
    return config, client_private, client_public
