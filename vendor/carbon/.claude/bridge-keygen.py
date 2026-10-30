#!/usr/bin/env python3
"""
Generate keypair for bridge WSS auth.

Run on each machine that needs bridge access:
  python bridge-keygen.py client    # generates bridge_client.key + bridge_client.pub
  python bridge-keygen.py server    # generates bridge.key + bridge.pub (VPS only)

The .pub file is safe to share. The .key file is the identity — keep it local.
"""
import sys
import os

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
except ImportError:
    print("pip install cryptography")
    sys.exit(1)

mode = sys.argv[1] if len(sys.argv) > 1 else 'client'
prefix = 'bridge' if mode == 'server' else 'bridge_client'

key = ec.generate_private_key(ec.SECP256R1())

key_path = f'{prefix}.key'
pub_path = f'{prefix}.pub'

with open(key_path, 'wb') as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    ))

with open(pub_path, 'wb') as f:
    f.write(key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    ))

print(f"Generated: {key_path} (PRIVATE — keep secret)")
print(f"Generated: {pub_path} (PUBLIC — safe to share)")
print(f"\nFor VPS: copy {pub_path} to /opt/services/bridge/allowed_clients/")
print(f"For client: keep {key_path} at C:\\claude\\shared\\{key_path}")
