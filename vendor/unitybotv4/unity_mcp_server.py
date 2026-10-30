"""
Unity MCP Server - Allows Claude CLI to monitor and respond through Discord as Unity
"""
import json
import sys
import requests
from datetime import datetime, timedelta

API_BASE = "http://localhost:5050"

# Track last checked timestamp
last_check_time = None

def get_status():
    """Check if Unity bot is online and API is running."""
    try:
        resp = requests.get(f"{API_BASE}/claude/status", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e), "status": "offline"}

def read_messages(limit=20, since=None):
    """Read recent messages from the Discord channel."""
    try:
        params = {"limit": limit}
        if since:
            params["since"] = since
        resp = requests.get(f"{API_BASE}/claude/read", params=params, timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e), "messages": []}

def post_message(message, prefix=""):
    """Post a message to Discord as Unity."""
    try:
        resp = requests.post(
            f"{API_BASE}/claude/post",
            json={"message": message, "prefix": prefix},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def check_for_mentions():
    """Check for new messages that mention Claude/Unity and need a response."""
    global last_check_time

    # Get messages since last check
    since = last_check_time
    if not since:
        # First check - get last 10 messages
        data = read_messages(limit=10)
    else:
        data = read_messages(since=since)

    # Update last check time
    last_check_time = datetime.utcnow().isoformat()

    messages = data.get("messages", [])

    # Filter for messages that might need Claude CLI response
    # Look for: mentions of "claude", "cli", direct questions, etc.
    triggers = ["claude", "cli", "hey unity", "unity?", "@unity", "real claude", "actual claude"]

    needs_response = []
    for msg in messages:
        # Skip messages from Unity itself
        if msg.get("from_claude") == "unity":
            continue

        content_lower = msg.get("content", "").lower()

        # Check if any trigger words are present
        for trigger in triggers:
            if trigger in content_lower:
                needs_response.append(msg)
                break

    return {
        "new_messages": len(messages),
        "needs_response": needs_response,
        "last_check": last_check_time
    }

def handle_request(request):
    """Handle incoming MCP requests."""
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "unity_status",
                    "description": "Check if Unity Discord bot is online and API is running",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "unity_read",
                    "description": "Read recent messages from the Unity Discord channel",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Number of messages to read (default 20)"},
                            "since": {"type": "string", "description": "ISO timestamp to read messages since"}
                        }
                    }
                },
                {
                    "name": "unity_post",
                    "description": "Post a message to Discord as Unity (Gee's Unity)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "The message to post"},
                            "prefix": {"type": "string", "description": "Optional prefix like 'G>' for the message"}
                        },
                        "required": ["message"]
                    }
                },
                {
                    "name": "unity_check",
                    "description": "Check for new messages that need Claude CLI to respond (mentions of claude, cli, etc.)",
                    "inputSchema": {"type": "object", "properties": {}}
                }
            ]
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "unity_status":
            result = get_status()
        elif tool_name == "unity_read":
            result = read_messages(
                limit=args.get("limit", 20),
                since=args.get("since")
            )
        elif tool_name == "unity_post":
            result = post_message(
                message=args.get("message", ""),
                prefix=args.get("prefix", "")
            )
        elif tool_name == "unity_check":
            result = check_for_mentions()
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
        }

    return {"error": "Unknown method"}

def main():
    """Main MCP server loop."""
    # Read JSON-RPC requests from stdin
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": str(e)}
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    main()
