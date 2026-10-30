#!/usr/bin/env python3
"""
Bridge Chat MCP — lets bots send/receive messages through the VPS bridge.
WSS + public-key challenge-response auth. No passwords.
Server: wss://admin.entercarbon.com/bridge/ (nginx proxy)
Client key: C:\claude\shared\bridge_client.key
"""
import sys
import json
import os
import time
import urllib.request
import urllib.error
import traceback

sys.stdin.reconfigure(encoding='utf-8', errors='replace')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def _log(msg):
    """Log to stderr so Claude Code can see MCP server diagnostics."""
    print(f"[bridge-mcp] {msg}", file=sys.stderr, flush=True)

_log("Starting bridge MCP server...")

# Add shared path so we can import bridge_client_wss
sys.path.insert(0, r'C:\claude\shared')

MY_NAME = os.environ.get('CLAUDE_BOT_NAME', 'Unity')

# Admin API base URL (local game server admin panel)
ADMIN_URL = os.environ.get('ADMIN_URL', 'http://localhost:3001')

# Track last poll time per channel
_last_poll = {}

# WSS bridge client — public-key auth, no passwords
try:
    import bridge_client_wss as _bridge
    _bridge_available = True
    _log("bridge_client_wss imported OK")
except ImportError as e:
    _bridge_available = False
    _log(f"bridge_client_wss import FAILED: {e}")
except Exception as e:
    _bridge_available = False
    _log(f"bridge_client_wss import ERROR: {e}")


def send_response(r):
    print(json.dumps(r), flush=True)

def send_result(i, r):
    send_response({"jsonrpc": "2.0", "id": i, "result": r})

def send_error(i, c, m):
    send_response({"jsonrpc": "2.0", "id": i, "error": {"code": c, "message": m}})


def bridge_send(args):
    """Send a message to the bridge chat via WSS."""
    text = args.get('text', '')
    channel = args.get('channel', 'default')
    name = args.get('as', MY_NAME)

    if not text:
        return {"content": [{"type": "text", "text": "Error: 'text' required"}]}
    if not _bridge_available:
        return {"content": [{"type": "text", "text": "Error: bridge_client_wss not available. pip install websockets cryptography"}]}

    result, err = _bridge.send_message_sync(name, text, channel)
    if err:
        return {"content": [{"type": "text", "text": f"Error: {err}"}]}
    return {"content": [{"type": "text", "text": f"Sent to bridge ({len(text)} chars)"}]}


def bridge_read(args):
    """Read recent messages from the bridge chat via WSS."""
    channel = args.get('channel', 'default')
    limit = args.get('limit', 20)
    since = args.get('since', 0)

    if not _bridge_available:
        return {"content": [{"type": "text", "text": "Error: bridge_client_wss not available. pip install websockets cryptography"}]}

    if since == 0:
        since = _last_poll.get(channel, 0)

    msgs, err = _bridge.read_messages_sync(since, channel, limit)
    if err:
        return {"content": [{"type": "text", "text": f"Error: {err}"}]}
    if not msgs:
        return {"content": [{"type": "text", "text": "No new messages."}]}

    _last_poll[channel] = max(m.get('ts', 0) for m in msgs)

    lines = []
    for m in msgs:
        ts = time.strftime('%H:%M', time.localtime(m.get('ts', 0)))
        lines.append(f"[{ts}] {m.get('from', '?')}: {m.get('text', '')}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def bridge_history(args):
    """Read full message history from bridge chat via WSS."""
    channel = args.get('channel', 'default')
    limit = args.get('limit', 50)

    if not _bridge_available:
        return {"content": [{"type": "text", "text": "Error: bridge_client_wss not available. pip install websockets cryptography"}]}

    msgs, err = _bridge.read_messages_sync(0, channel, limit)
    if err:
        return {"content": [{"type": "text", "text": f"Error: {err}"}]}
    if not msgs:
        return {"content": [{"type": "text", "text": "No messages in history."}]}

    _last_poll[channel] = max(m.get('ts', 0) for m in msgs)

    lines = []
    for m in msgs:
        ts = time.strftime('%H:%M', time.localtime(m.get('ts', 0)))
        lines.append(f"[{ts}] {m.get('from', '?')}: {m.get('text', '')}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def bridge_send_file(args):
    """Upload a file to the bridge — not yet supported on WSS bridge."""
    return {"content": [{"type": "text", "text": "File upload not yet supported on WSS bridge. Use bridge_send with text content instead."}]}


def bridge_list_files(args):
    """List files on the bridge — not yet supported on WSS bridge."""
    return {"content": [{"type": "text", "text": "File listing not yet supported on WSS bridge."}]}


def bridge_get_file(args):
    """Download a file — not yet supported on WSS bridge."""
    return {"content": [{"type": "text", "text": "File download not yet supported on WSS bridge."}]}


def bridge_delete_file(args):
    """Delete a file — not yet supported on WSS bridge."""
    return {"content": [{"type": "text", "text": "File deletion not yet supported on WSS bridge."}]}


# ── Admin API Tools (localhost:3001) ──

def _admin_api(method, path, data=None):
    """Make an API call to the local admin server."""
    url = f"{ADMIN_URL}{path}"
    headers = {'Content-Type': 'application/json'}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode()
            return {'error': f'HTTP {e.code}: {err_body}'}
        except:
            return {'error': f'HTTP {e.code}: {e.reason}'}
    except Exception as e:
        return {'error': str(e)}


def admin_servers(args):
    """List all game servers."""
    result = _admin_api('GET', '/api/servers')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}

    servers = result.get('servers', [])
    if not servers:
        return {"content": [{"type": "text", "text": "No servers. Create one with admin_create_server."}]}

    lines = []
    for s in servers:
        lines.append(f"[{s.get('id','')}] {s.get('name','')} — {s.get('status','?')} | ws:{s.get('ws_port','')} | players:{s.get('player_count',0)} | year:{s.get('game_year','')} {s.get('eon','')}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def admin_create_server(args):
    """Create a new game server."""
    name = args.get('name', 'New Server')
    result = _admin_api('POST', '/api/servers', {'name': name})
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    s = result.get('server', result)
    return {"content": [{"type": "text", "text": f"Created server: {s.get('id','')} ({s.get('name','')}) ws:{s.get('ws_port','')}"}]}


def admin_server_action(args):
    """Start, stop, or restart a game server."""
    server_id = args.get('server_id', '')
    action = args.get('action', '')
    if not server_id:
        return {"content": [{"type": "text", "text": "Error: server_id required"}]}
    if action not in ('start', 'stop', 'restart'):
        return {"content": [{"type": "text", "text": "Error: action must be start, stop, or restart"}]}

    result = _admin_api('POST', f'/api/servers/{server_id}/{action}')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    s = result.get('server', result)
    return {"content": [{"type": "text", "text": f"Server {server_id} → {action}: {s.get('status', 'ok')}"}]}


def admin_server_config(args):
    """Get or update a server's config."""
    server_id = args.get('server_id', '')
    config = args.get('config', None)
    if not server_id:
        return {"content": [{"type": "text", "text": "Error: server_id required"}]}

    if config:
        result = _admin_api('PUT', f'/api/servers/{server_id}/config', config)
    else:
        result = _admin_api('GET', f'/api/servers/{server_id}')

    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)[:3000]}]}


def admin_server_logs(args):
    """Get console logs from a game server."""
    server_id = args.get('server_id', '')
    lines = args.get('lines', 100)
    if not server_id:
        return {"content": [{"type": "text", "text": "Error: server_id required"}]}

    result = _admin_api('GET', f'/api/servers/{server_id}/console?lines={lines}')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}

    logs = result.get('logs', [])
    if not logs:
        return {"content": [{"type": "text", "text": "No logs."}]}

    out = []
    for entry in logs[-int(lines):]:
        ts = time.strftime('%H:%M:%S', time.localtime(entry.get('ts', 0) / 1000))
        out.append(f"[{ts}] {entry.get('level','')}: {entry.get('text','')}")
    return {"content": [{"type": "text", "text": "\n".join(out)[:4000]}]}


def admin_players(args):
    """List players on a game server."""
    server_id = args.get('server_id', '')
    if not server_id:
        return {"content": [{"type": "text", "text": "Error: server_id required"}]}

    result = _admin_api('GET', f'/api/servers/{server_id}/players')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}

    players = result.get('players', [])
    if not players:
        return {"content": [{"type": "text", "text": "No players online."}]}

    lines = []
    for p in players:
        lines.append(f"[{p.get('id','')}] {p.get('name','')} — HP:{p.get('hp','')} loc:({p.get('x','')},{p.get('y','')})")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def admin_delete_server(args):
    """Delete a game server."""
    server_id = args.get('server_id', '')
    if not server_id:
        return {"content": [{"type": "text", "text": "Error: server_id required"}]}

    result = _admin_api('DELETE', f'/api/servers/{server_id}')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    return {"content": [{"type": "text", "text": f"Deleted server {server_id}"}]}


def admin_db_stats(args):
    """Get row counts for all Supabase tables."""
    result = _admin_api('GET', '/api/db/stats')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    lines = [f"  {t}: {c} rows" for t, c in result.items()]
    return {"content": [{"type": "text", "text": "Database stats:\n" + "\n".join(lines)}]}


def admin_db_clear_table(args):
    """Clear all rows from a specific Supabase table."""
    table = args.get('table', '')
    if not table:
        return {"content": [{"type": "text", "text": "Error: table name required"}]}
    result = _admin_api('DELETE', f'/api/db/table/{table}')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    return {"content": [{"type": "text", "text": f"Cleared table: {table}"}]}


def admin_db_reset(args):
    """Nuclear reset: wipe ALL game data from Supabase + local registry."""
    result = _admin_api('POST', '/api/db/reset')
    if 'error' in result:
        return {"content": [{"type": "text", "text": f"Error: {result['error']}"}]}
    tables = result.get('tables', {})
    lines = [f"  {t}: {s}" for t, s in tables.items()]
    return {"content": [{"type": "text", "text": "Full reset complete:\n" + "\n".join(lines)}]}


TOOLS = [
    {
        "name": "bridge_send",
        "description": "Send a message to the bridge chat. Messages are visible to anyone connected (Gee, Unity, other bots).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Message text to send"},
                "channel": {"type": "string", "description": "Chat channel (default: 'default')"},
                "as": {"type": "string", "description": "Send as this name (default: bot name)"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "bridge_read",
        "description": "Read new messages from the bridge chat since last check.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Chat channel (default: 'default')"},
                "limit": {"type": "integer", "description": "Max messages to return (default: 20)"},
                "since": {"type": "number", "description": "Unix timestamp to read from (default: last poll time)"}
            }
        }
    },
    {
        "name": "bridge_history",
        "description": "Read full message history from the bridge chat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Chat channel (default: 'default')"},
                "limit": {"type": "integer", "description": "Max messages to return (default: 50)"}
            }
        }
    },
    {
        "name": "bridge_send_file",
        "description": "Upload a file to the bridge. Images show inline, audio plays inline, other files as download links.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local file path to upload"},
                "text": {"type": "string", "description": "Optional message to accompany the file"},
                "channel": {"type": "string", "description": "Chat channel (default: 'default')"},
                "as": {"type": "string", "description": "Send as this name (default: bot name)"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "bridge_list_files",
        "description": "List files shared on the bridge with download URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "bridge_get_file",
        "description": "Download a file from the bridge to local disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "File ID from bridge_list_files"},
                "save_to": {"type": "string", "description": "Local path to save the file"}
            },
            "required": ["file_id", "save_to"]
        }
    },
    {
        "name": "bridge_delete_file",
        "description": "Delete a shared file from the bridge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "File ID to delete"}
            },
            "required": ["file_id"]
        }
    },
    {
        "name": "admin_servers",
        "description": "List all game servers with status, ports, player count, and game year.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "admin_create_server",
        "description": "Create a new game server instance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Server name (default: 'New Server')"}
            }
        }
    },
    {
        "name": "admin_server_action",
        "description": "Start, stop, or restart a game server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "Server ID"},
                "action": {"type": "string", "enum": ["start", "stop", "restart"], "description": "Action to perform"}
            },
            "required": ["server_id", "action"]
        }
    },
    {
        "name": "admin_server_config",
        "description": "Get or update a server's config. Pass config object to update, omit to read.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "Server ID"},
                "config": {"type": "object", "description": "Config to set (omit to read current config)"}
            },
            "required": ["server_id"]
        }
    },
    {
        "name": "admin_server_logs",
        "description": "Get console logs from a running game server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "Server ID"},
                "lines": {"type": "integer", "description": "Number of log lines (default: 100)"}
            },
            "required": ["server_id"]
        }
    },
    {
        "name": "admin_players",
        "description": "List online players on a game server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "Server ID"}
            },
            "required": ["server_id"]
        }
    },
    {
        "name": "admin_delete_server",
        "description": "Delete a game server instance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "server_id": {"type": "string", "description": "Server ID"}
            },
            "required": ["server_id"]
        }
    },
    {
        "name": "admin_db_stats",
        "description": "Get row counts for all Supabase game tables.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "admin_db_clear_table",
        "description": "Clear all rows from a specific Supabase table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Table name (servers, characters, inventory_items, skills, discoveries, known_recipes, server_history, world_chunks, groups, group_members)"}
            },
            "required": ["table"]
        }
    },
    {
        "name": "admin_db_reset",
        "description": "Nuclear reset: wipe ALL Supabase game data + local registry. Fresh slate.",
        "inputSchema": {"type": "object", "properties": {}}
    },
]

HANDLERS = {
    "bridge_send": bridge_send,
    "bridge_read": bridge_read,
    "bridge_history": bridge_history,
    "bridge_send_file": bridge_send_file,
    "bridge_list_files": bridge_list_files,
    "bridge_get_file": bridge_get_file,
    "bridge_delete_file": bridge_delete_file,
    "admin_servers": admin_servers,
    "admin_create_server": admin_create_server,
    "admin_server_action": admin_server_action,
    "admin_server_config": admin_server_config,
    "admin_server_logs": admin_server_logs,
    "admin_players": admin_players,
    "admin_delete_server": admin_delete_server,
    "admin_db_stats": admin_db_stats,
    "admin_db_clear_table": admin_db_clear_table,
    "admin_db_reset": admin_db_reset,
}


def main():
    _log(f"MCP server ready — reading stdin (bridge={'OK' if _bridge_available else 'UNAVAILABLE'}, name={MY_NAME})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
            method = m.get("method")
            i = m.get("id")
            p = m.get("params", {})

            if method == "initialize":
                _log("Received initialize")
                send_result(i, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "bridge_chat", "version": "2.0"}
                })
                _log("Sent initialize response")
            elif method == "notifications/initialized":
                _log("Client initialized notification received")
            elif method == "tools/list":
                _log(f"tools/list requested — returning {len(TOOLS)} tools")
                send_result(i, {"tools": TOOLS})
            elif method == "tools/call":
                tool_name = p.get("name", "?")
                _log(f"tools/call: {tool_name}")
                h = HANDLERS.get(tool_name)
                if h:
                    try:
                        result = h(p.get("arguments", {}))
                        send_result(i, result)
                        _log(f"tools/call {tool_name}: OK")
                    except Exception as e:
                        _log(f"tools/call {tool_name} HANDLER ERROR: {e}\n{traceback.format_exc()}")
                        send_result(i, {"content": [{"type": "text", "text": f"Error in {tool_name}: {e}"}]})
                else:
                    send_error(i, -32601, f"Unknown tool: {tool_name}")
            elif method and method.startswith("notifications/"):
                pass  # silently ignore other notifications
            elif i:
                send_error(i, -32601, f"Unknown method: {method}")
        except json.JSONDecodeError as e:
            _log(f"JSON parse error: {e} — line: {line[:200]}")
        except Exception as e:
            _log(f"Unhandled error: {e}\n{traceback.format_exc()}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        _log("Shutting down (KeyboardInterrupt)")
    except Exception as e:
        _log(f"FATAL: {e}\n{traceback.format_exc()}")
        sys.exit(1)
