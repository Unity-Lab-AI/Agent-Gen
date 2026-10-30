#!/usr/bin/env python3
"""
Discord MCP Server for Unity (Gee's Claude)
Wraps discord_bot.py queue/inbox as MCP tools for Claude Code CLI.

Add to your Claude settings.json:
{
  "mcpServers": {
    "discord": {
      "command": "python",
      "args": ["path/to/discord_mcp.py"]
    }
  }
}
"""
import sys, json
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent
INBOX_FILE = BASE_DIR / "discord_inbox.json"
QUEUE_FILE = BASE_DIR / "discord_send_queue.json"

def send_response(r): print(json.dumps(r), flush=True)
def send_error(i, c, m): send_response({"jsonrpc": "2.0", "id": i, "error": {"code": c, "message": m}})
def send_result(i, r): send_response({"jsonrpc": "2.0", "id": i, "result": r})

def queue_message(msg_type, content, **kwargs):
    queue = []
    if QUEUE_FILE.exists():
        try: queue = json.loads(QUEUE_FILE.read_text())
        except: queue = []
    item = {"type": msg_type, "content": content, "queued_at": datetime.now().isoformat(), "sent": False, **kwargs}
    queue.append(item)
    QUEUE_FILE.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding='utf-8')
    return len([q for q in queue if not q.get('sent')])

def discord_send(args):
    text = args.get('text', '')
    if not text:
        return {"content": [{"type": "text", "text": "Error: 'text' required"}]}
    pending = queue_message("channel", text)
    return {"content": [{"type": "text", "text": f"Queued message ({len(text)} chars). {pending} pending."}]}

def discord_inbox(args):
    limit = args.get('limit', 10)
    if not INBOX_FILE.exists():
        return {"content": [{"type": "text", "text": "No messages in inbox"}]}
    try:
        inbox = json.loads(INBOX_FILE.read_text())
        if not inbox:
            return {"content": [{"type": "text", "text": "Inbox empty"}]}
        lines = [f"Last {min(limit, len(inbox))} messages:"]
        for msg in inbox[-limit:]:
            ts = msg.get('ts', '')[:16]
            author = msg.get('author', 'unknown')[:15]
            content = msg.get('content', '')[:200]
            mention = "[!]" if msg.get('mention') else ""
            lines.append(f"{ts} {author} {mention}: {content}")
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}
    except:
        return {"content": [{"type": "text", "text": "Error reading inbox"}]}

def discord_status(args):
    pending = 0
    if QUEUE_FILE.exists():
        try:
            queue = json.loads(QUEUE_FILE.read_text())
            pending = len([q for q in queue if not q.get('sent')])
        except: pass
    inbox_count = 0
    if INBOX_FILE.exists():
        try:
            inbox = json.loads(INBOX_FILE.read_text())
            inbox_count = len(inbox)
        except: pass
    return {"content": [{"type": "text", "text": f"Queue: {pending} pending\nInbox: {inbox_count} messages"}]}

def discord_clear_queue(args):
    if QUEUE_FILE.exists():
        try:
            queue = json.loads(QUEUE_FILE.read_text())
            queue = [q for q in queue if q.get('sent')]
            QUEUE_FILE.write_text(json.dumps(queue, indent=2))
            return {"content": [{"type": "text", "text": "Queue cleared"}]}
        except:
            return {"content": [{"type": "text", "text": "Error clearing queue"}]}
    return {"content": [{"type": "text", "text": "No queue file"}]}

TOOLS = [
    {"name": "discord_send", "description": "Send message to the XPSOLD collaboration channel", "inputSchema": {
        "type": "object", "properties": {"text": {"type": "string", "description": "Message text"}}, "required": ["text"]}},
    {"name": "discord_inbox", "description": "Read recent Discord messages from the channel", "inputSchema": {
        "type": "object", "properties": {"limit": {"type": "integer", "description": "Max messages (default 10)"}}, "required": []}},
    {"name": "discord_status", "description": "Check Discord queue and inbox status", "inputSchema": {
        "type": "object", "properties": {}, "required": []}},
    {"name": "discord_clear_queue", "description": "Clear unsent messages from queue", "inputSchema": {
        "type": "object", "properties": {}, "required": []}}
]

HANDLERS = {
    "discord_send": discord_send,
    "discord_inbox": discord_inbox,
    "discord_status": discord_status,
    "discord_clear_queue": discord_clear_queue
}

def main():
    for line in sys.stdin:
        try:
            m = json.loads(line)
            method, i, p = m.get("method"), m.get("id"), m.get("params", {})
            if method == "initialize":
                send_result(i, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "discord", "version": "1.0"}})
            elif method == "notifications/initialized":
                pass
            elif method == "tools/list":
                send_result(i, {"tools": TOOLS})
            elif method == "tools/call":
                h = HANDLERS.get(p.get("name"))
                if h: send_result(i, h(p.get("arguments", {})))
                else: send_error(i, -32601, f"Unknown: {p.get('name')}")
            elif i:
                send_error(i, -32601, f"Unknown: {method}")
        except: pass

if __name__ == "__main__":
    main()
