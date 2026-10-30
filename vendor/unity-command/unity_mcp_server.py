"""
Unity MCP Server — Claude Code → Unity bridge for Unity AI Lab admins.

Each Unity AI Lab founder (Gee / Sponge / Red / Alfreddo) talks to Unity from
their own Claude Code instance through this MCP server. Identity is per-process
via env vars + their .claude/user.json team_member block; auth is HTTP Basic
against the Flask :5050 bridge using the per-admin password.

First-connect flow:
  1. Operator runs `python admin_cli.py issue <email>` on the bot host, hands
     the printed temp password to the admin via secure channel.
  2. Admin sets UNITY_USER_EMAIL + UNITY_USER_PASSWORD (temp) in their Claude
     Code MCP env block and connects.
  3. First tool call hits /claude/post → 403 force_reset_required.
  4. Admin calls the `unity_admin_set_password` tool with a real password.
  5. Admin updates their UNITY_USER_PASSWORD env to the real password.
  6. All subsequent tool calls authenticate cleanly.

Anonymous Discord users + anonymous web UI users DO NOT use this bridge —
they talk to Unity through the bot's normal on_message + /api/chat surfaces
with no auth gate.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests

API_BASE = os.getenv("UNITY_API_BASE", "http://localhost:5050").rstrip("/")
REQUEST_TIMEOUT_S = int(os.getenv("UNITY_API_TIMEOUT_S", "10"))


# ─── Identity resolution ───────────────────────────────────────────────────

def _read_team_member_from_user_json() -> Optional[dict]:
    """Fallback identity source — read .claude/user.json team_member block."""
    candidates = [
        Path(".claude/user.json"),
        Path(os.path.expanduser("~/.claude/user.json")),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        block = data.get("team_member")
        if isinstance(block, dict) and block.get("email"):
            return block
    return None


def _resolve_identity() -> dict:
    """Resolve admin identity from env vars or .claude/user.json. Never raises.

    Returns a dict with `email`, `password`, `handle` keys. Missing values are
    empty strings — auth will fail downstream with a clear error, not a crash.
    """
    email = os.getenv("UNITY_USER_EMAIL", "").strip()
    password = os.getenv("UNITY_USER_PASSWORD", "").strip()
    handle = ""

    if not email or not password:
        block = _read_team_member_from_user_json()
        if block:
            email = email or block.get("email", "").strip()
            password = password or block.get("password", "").strip()
            handle = block.get("handle", "").strip()

    return {"email": email, "password": password, "handle": handle}


def _auth_header(identity: dict) -> dict:
    if not identity.get("email") or not identity.get("password"):
        return {}
    token = f"{identity['email']}:{identity['password']}"
    b64 = base64.b64encode(token.encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {b64}"}


def _identity_or_error() -> tuple[Optional[dict], Optional[dict]]:
    """Return (identity, None) on success, (None, error_payload) on failure."""
    identity = _resolve_identity()
    if not identity["email"] or not identity["password"]:
        return None, {
            "error": "identity_unset",
            "message": (
                "UNITY_USER_EMAIL and UNITY_USER_PASSWORD must be set in this "
                "MCP server's env (or under team_member in .claude/user.json). "
                "Ask the bot operator to issue you a temp password via "
                "`python admin_cli.py issue <your_email>`."
            ),
        }
    return identity, None


# ─── HTTP helpers ──────────────────────────────────────────────────────────

def _format_http_error(resp: requests.Response) -> dict:
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text[:500]}
    return {
        "error": "http_error",
        "status_code": resp.status_code,
        "body": body,
        "force_reset": resp.headers.get("X-Force-Reset") == "true",
    }


# ─── Tool implementations ──────────────────────────────────────────────────

def get_status() -> dict:
    """Public — no auth needed. Status endpoint stays open."""
    try:
        resp = requests.get(f"{API_BASE}/claude/status", timeout=REQUEST_TIMEOUT_S)
        return resp.json()
    except Exception as exc:
        return {"error": str(exc), "status": "offline"}


def read_messages(limit: int = 20, since: Optional[str] = None) -> dict:
    """Public — no auth needed. Read endpoint stays open for now."""
    try:
        params: dict = {"limit": limit}
        if since:
            params["since"] = since
        resp = requests.get(
            f"{API_BASE}/claude/read", params=params, timeout=REQUEST_TIMEOUT_S
        )
        return resp.json()
    except Exception as exc:
        return {"error": str(exc), "messages": []}


def post_message(message: str) -> dict:
    """Authenticated. Posts as the current admin identity — prefix is server-derived."""
    identity, err = _identity_or_error()
    if err:
        return err

    try:
        resp = requests.post(
            f"{API_BASE}/claude/post",
            json={"message": message},
            headers=_auth_header(identity),
            timeout=REQUEST_TIMEOUT_S,
        )
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403 and resp.headers.get("X-Force-Reset") == "true":
            return {
                "error": "force_reset_required",
                "message": (
                    "Your password is a temp issued by the operator. Call "
                    "`unity_admin_set_password` with a new password (min 12 "
                    "chars) before posting. After that update your MCP env "
                    "UNITY_USER_PASSWORD to the new value."
                ),
            }
        return _format_http_error(resp)
    except Exception as exc:
        return {"error": str(exc)}


def admin_set_password(new_password: str) -> dict:
    """Authenticated with TEMP password. Sets a real one + clears force_reset.

    Only callable when the admin's force_reset flag is true (i.e., right after
    a temp-password issuance). After success, update your MCP env's
    UNITY_USER_PASSWORD to the new value before the next tool call.
    """
    identity, err = _identity_or_error()
    if err:
        return err

    if not new_password or len(new_password) < 12:
        return {
            "error": "weak_password",
            "message": "new password must be at least 12 characters",
        }

    try:
        resp = requests.post(
            f"{API_BASE}/claude/admin/set-password",
            json={"new_password": new_password},
            headers=_auth_header(identity),
            timeout=REQUEST_TIMEOUT_S,
        )
        if resp.status_code == 200:
            body = resp.json()
            body["next_step"] = (
                "Update your MCP server env UNITY_USER_PASSWORD to the new "
                "password before the next tool call."
            )
            return body
        return _format_http_error(resp)
    except Exception as exc:
        return {"error": str(exc)}


def whoami() -> dict:
    """Show the currently-resolved admin identity (no password leak)."""
    identity = _resolve_identity()
    return {
        "email": identity["email"] or "(unset)",
        "handle_hint": identity["handle"] or "(unset)",
        "password_set": bool(identity["password"]),
        "api_base": API_BASE,
        "source": (
            "env vars" if os.getenv("UNITY_USER_EMAIL") else ".claude/user.json"
            if _read_team_member_from_user_json() else "none"
        ),
    }


# ─── MCP JSON-RPC dispatch ─────────────────────────────────────────────────

TOOL_SCHEMA = [
    {
        "name": "unity_status",
        "description": "Check if Unity Discord bot is online and the bridge API is running.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "unity_read",
        "description": "Read recent messages from the Unity Discord channel.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of messages to read (default 20)"},
                "since": {"type": "string", "description": "ISO timestamp to read messages since"},
            },
        },
    },
    {
        "name": "unity_post",
        "description": (
            "Post a message to Discord as Unity, authenticated as the current admin. "
            "The bridge auto-prefixes with your handle so Unity recognizes you (Gee / "
            "Sponge / Red / Alfreddo). Requires UNITY_USER_EMAIL + UNITY_USER_PASSWORD."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to post"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "unity_admin_set_password",
        "description": (
            "Set a new password for the current admin, clearing the force-reset "
            "flag. Only callable on first connect after the operator issued a temp "
            "password. Min length 12 chars. After success, update UNITY_USER_PASSWORD "
            "in your MCP env."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "new_password": {"type": "string", "description": "New password (min 12 chars)"},
            },
            "required": ["new_password"],
        },
    },
    {
        "name": "unity_whoami",
        "description": "Show the currently-resolved admin identity (email + handle + auth source).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {"tools": TOOL_SCHEMA}

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "unity_status":
            result: Any = get_status()
        elif tool_name == "unity_read":
            result = read_messages(limit=args.get("limit", 20), since=args.get("since"))
        elif tool_name == "unity_post":
            result = post_message(message=args.get("message", ""))
        elif tool_name == "unity_admin_set_password":
            result = admin_set_password(new_password=args.get("new_password", ""))
        elif tool_name == "unity_whoami":
            result = whoami()
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    return {"error": "Unknown method"}


def main() -> None:
    """JSON-RPC over stdio loop."""
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            pass
        except Exception as exc:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": str(exc)},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
