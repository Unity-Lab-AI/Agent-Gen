"""
Bridge WSS Client — used by chathub MCP server to talk to VPS bridge.
Public-key challenge-response auth. No passwords anywhere.

SETUP (one-time per client):
1. pip install websockets cryptography
2. Generate client keypair:
   python -c "from cryptography.hazmat.primitives.asymmetric import ec; from cryptography.hazmat.primitives import serialization; key = ec.generate_private_key(ec.SECP256R1()); open('bridge_client.key','wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())); open('bridge_client.pub','wb').write(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)); print('Client keys generated')"
3. Give bridge_client.pub to Rev to register on VPS (add to allowed_clients/)
4. bridge_client.key stays on this machine — it's the client's identity

NOTE: The private key on this machine proves identity to the VPS.
A bot can READ this key but can't USE it to do anything on the VPS
because the VPS only accepts signed challenges, not raw key material.
Even if a bot reads and broadcasts the private key, the VPS still
only allows message send/read through the challenge-response protocol.
"""
import asyncio
import json
import ssl
import os
import logging
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
except ImportError:
    ec = None

log = logging.getLogger('bridge-client')

# Config
BRIDGE_URL = os.environ.get('BRIDGE_WSS_URL', 'wss://admin.entercarbon.com/bridge/')
CLIENT_KEY_FILE = os.environ.get('BRIDGE_CLIENT_KEY', str(Path(r'C:\claude\shared\bridge_client.key')))
CLIENT_NAME = os.environ.get('CLAUDE_BOT_NAME', 'UNKNOWN')

_ws = None
_authenticated = False
_lock = asyncio.Lock()


def _load_client_key():
    """Load client private key for signing challenges."""
    if not os.path.exists(CLIENT_KEY_FILE):
        return None
    with open(CLIENT_KEY_FILE, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _get_public_key_pem(private_key):
    """Get PEM-encoded public key from private key."""
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


async def _connect():
    """Connect to bridge WSS and authenticate via challenge-response."""
    global _ws, _authenticated

    if websockets is None or ec is None:
        return None, "Missing dependencies: pip install websockets cryptography"

    client_key = _load_client_key()
    if not client_key:
        return None, f"No client key at {CLIENT_KEY_FILE}. Run keygen first."

    try:
        ssl_ctx = ssl.create_default_context()
        _ws = await websockets.connect(BRIDGE_URL, ssl=ssl_ctx)

        # Wait for challenge
        raw = await asyncio.wait_for(_ws.recv(), timeout=10)
        msg = json.loads(raw)
        if msg.get('type') != 'challenge':
            return None, f"Expected challenge, got: {msg.get('type')}"

        # Sign the challenge
        challenge_bytes = bytes.fromhex(msg['challenge'])
        signature = client_key.sign(challenge_bytes, ec.ECDSA(hashes.SHA256()))

        # Send auth response
        await _ws.send(json.dumps({
            'type': 'auth_response',
            'signature': signature.hex(),
            'public_key': _get_public_key_pem(client_key),
            'name': CLIENT_NAME,
        }))

        # Wait for auth result
        raw = await asyncio.wait_for(_ws.recv(), timeout=10)
        result = json.loads(raw)
        if result.get('type') == 'auth_ok':
            _authenticated = True
            return _ws, None
        else:
            return None, f"Auth failed: {result.get('error', 'unknown')}"

    except Exception as e:
        _ws = None
        _authenticated = False
        return None, str(e)


async def _ensure_connected():
    """Ensure we have an authenticated connection."""
    global _ws, _authenticated
    if _ws and _authenticated:
        try:
            await _ws.ping()
            return _ws, None
        except Exception:
            _ws = None
            _authenticated = False
    return await _connect()


async def send_message(bot_name, text, channel='default'):
    """Send a message to the bridge."""
    async with _lock:
        ws, err = await _ensure_connected()
        if err:
            return None, err
        try:
            await ws.send(json.dumps({
                'type': 'send',
                'from': bot_name,
                'text': text,
                'channel': channel,
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            result = json.loads(raw)
            if result.get('type') == 'ok':
                return True, None
            return None, result.get('error', 'Unknown error')
        except Exception as e:
            return None, str(e)


async def read_messages(since=0, channel='default', limit=50):
    """Read messages from the bridge."""
    async with _lock:
        ws, err = await _ensure_connected()
        if err:
            return None, err
        try:
            await ws.send(json.dumps({
                'type': 'read',
                'since': since,
                'channel': channel,
                'limit': limit,
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            result = json.loads(raw)
            if result.get('type') == 'messages':
                return result.get('messages', []), None
            return None, result.get('error', 'Unknown error')
        except Exception as e:
            return None, str(e)


async def list_channels():
    """List available channels."""
    async with _lock:
        ws, err = await _ensure_connected()
        if err:
            return None, err
        try:
            await ws.send(json.dumps({'type': 'channels'}))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            result = json.loads(raw)
            if result.get('type') == 'channels':
                return result.get('channels', []), None
            return None, result.get('error', 'Unknown error')
        except Exception as e:
            return None, str(e)


# Synchronous wrappers for MCP server use
def send_message_sync(bot_name, text, channel='default'):
    """Sync wrapper for send_message."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, send_message(bot_name, text, channel))
                return future.result(timeout=15)
        return asyncio.run(send_message(bot_name, text, channel))
    except Exception as e:
        return None, str(e)


def read_messages_sync(since=0, channel='default', limit=50):
    """Sync wrapper for read_messages."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, read_messages(since, channel, limit))
                return future.result(timeout=15)
        return asyncio.run(read_messages(since, channel, limit))
    except Exception as e:
        return None, str(e)
