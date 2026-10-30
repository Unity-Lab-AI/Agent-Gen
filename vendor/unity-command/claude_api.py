"""
Claude Chat API - REST API for Claude-to-Claude messaging through Discord.

Write endpoints (/claude/post, /claude/clear, /claude/admin/*) require HTTP
Basic auth against the Unity AI Lab founder roster managed by
`admin_credentials.py`. Read endpoints (/claude/status, /claude/read,
/claude/history, /healthz, /metrics) are open — anonymous Discord users + web
UI users bypass this bridge entirely via their own surfaces.
"""
import base64
import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from threading import Lock

import admin_credentials

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Thread-safe message storage
messages_lock = Lock()
claude_messages = []
MAX_MESSAGES = 100

# Reference to Discord bot (set during initialization)
discord_bot = None
discord_channel_id = None

def init_api(bot, channel_id):
    """Initialize the API with Discord bot reference + seed admin roster."""
    global discord_bot, discord_channel_id
    discord_bot = bot
    discord_channel_id = channel_id
    # Bootstrap the 4-founder credentials store on first run. Idempotent —
    # refuses to overwrite an existing file. Operator must explicitly issue
    # temp passwords via `python admin_cli.py issue <email>` before any admin
    # can authenticate against /claude/* write endpoints.
    try:
        admin_credentials.bootstrap_if_missing()
    except Exception as exc:
        logger.warning(f"Could not bootstrap admin credentials: {exc}")
    logger.info(f"Claude API initialized with channel ID: {channel_id}")


# ─── Auth middleware — admin-only gate on write endpoints ──────────────────

def _decode_basic_auth(header_value: str) -> tuple[str, str]:
    """Parse `Basic <b64(email:password)>` into (email, password). Empty on failure."""
    if not header_value or not header_value.lower().startswith("basic "):
        return "", ""
    try:
        decoded = base64.b64decode(header_value[6:].strip()).decode("utf-8")
        email, _, password = decoded.partition(":")
        return email.strip(), password
    except (ValueError, UnicodeDecodeError):
        return "", ""


def require_admin_auth(allow_force_reset: bool = False):
    """Decorator: require HTTP Basic auth from a Unity AI Lab founder.

    When `allow_force_reset=False` (default), responds 403 if the admin's
    force_reset flag is set — they must call /claude/admin/set-password first.
    When True (only on the set-password endpoint itself), allows the call to
    proceed so the admin can complete their first-connect flow.

    On success, the authenticated admin record is attached to `request.admin`.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            email, password = _decode_basic_auth(request.headers.get("Authorization", ""))
            if not email or not password:
                resp = jsonify({"error": "auth_required", "message": "HTTP Basic auth required (email:password)"})
                resp.headers["WWW-Authenticate"] = 'Basic realm="Unity AI Lab admin bridge"'
                return resp, 401

            admin = admin_credentials.authenticate(email, password)
            if admin is None:
                return jsonify({"error": "auth_failed", "message": "invalid email or password"}), 401

            if admin.get("force_reset") and not allow_force_reset:
                resp = jsonify({
                    "error": "force_reset_required",
                    "message": (
                        "Your password is a temp issued by the operator. Call "
                        "POST /claude/admin/set-password with `{new_password: ...}` "
                        "(min 12 chars) before this endpoint will accept your requests."
                    ),
                })
                resp.headers["X-Force-Reset"] = "true"
                return resp, 403

            # Attach the admin record so the view can look up handle/role.
            request.admin = admin  # type: ignore[attr-defined]
            return view(*args, **kwargs)

        return wrapped
    return decorator

def record_message(author_name: str, author_id: str, content: str, is_bot: bool = False):
    """Record a message from Discord to the local storage."""
    global claude_messages

    # Determine if this is from a Claude instance
    from_claude = None
    if is_bot:
        # Check for known Claude prefixes or bot patterns
        if "unity" in author_name.lower() or "gee" in author_name.lower():
            from_claude = "unity"
        elif "claude" in author_name.lower():
            from_claude = "claude"
        else:
            from_claude = author_name.lower()

    message_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "author": author_name,
        "author_id": str(author_id),
        "message": content,  # Use 'message' to match API spec
        "content": content,  # Keep for backwards compat
        "is_bot": is_bot,
        "from_claude": from_claude
    }

    with messages_lock:
        claude_messages.append(message_data)
        # Keep only the last MAX_MESSAGES
        if len(claude_messages) > MAX_MESSAGES:
            claude_messages = claude_messages[-MAX_MESSAGES:]

    _touch_activity()
    logger.debug(f"Recorded message from {author_name}: {content[:50]}...")

@app.route('/claude/status', methods=['GET'])
def get_status():
    """Check if the Claude API is running and connected."""
    return jsonify({
        "status": "online",
        "bot_connected": discord_bot is not None and not discord_bot.is_closed(),
        "channel_id": discord_channel_id,
        "messages_stored": len(claude_messages),  # Match API spec
        "message_count": len(claude_messages),
        "timestamp": datetime.utcnow().isoformat()
    })


# ─── Observability ───────────────────────────────────────────────────────────

# Tracking — first message timestamp + last activity timestamp. Used by
# /healthz to flag "no activity in N minutes" as degraded.
_first_seen_at = datetime.utcnow()
_last_activity_at = datetime.utcnow()


def _touch_activity():
    """Bump last-activity timestamp. Called from record_message + post_message."""
    global _last_activity_at
    _last_activity_at = datetime.utcnow()


@app.route('/healthz', methods=['GET'])
def healthz():
    """Health-check endpoint for monitoring / load balancers.

    Returns 200 when the bot is connected to Discord AND there's been activity
    (or fewer than 5 minutes since process start). Returns 503 when the bot is
    disconnected or activity has been idle longer than the configured threshold.

    Configurable via HEALTHZ_IDLE_THRESHOLD_SECONDS env (default 600 = 10 min).
    """
    bot_connected = discord_bot is not None and not discord_bot.is_closed()
    now = datetime.utcnow()
    uptime_s = (now - _first_seen_at).total_seconds()
    idle_s = (now - _last_activity_at).total_seconds()
    threshold = int(os.getenv("HEALTHZ_IDLE_THRESHOLD_SECONDS", "600"))

    healthy = True
    reasons = []
    if not bot_connected:
        # If a bot reference was registered, it must be connected.
        # Standalone web_server.py mode has no bot — that's OK.
        if discord_bot is not None:
            healthy = False
            reasons.append("discord bot disconnected")

    # Only flag idle if we've been up long enough for activity to be expected
    if uptime_s > threshold and idle_s > threshold and discord_bot is not None:
        healthy = False
        reasons.append(f"no activity in {int(idle_s)}s (threshold={threshold}s)")

    response = {
        "healthy": healthy,
        "bot_connected": bot_connected,
        "messages_stored": len(claude_messages),
        "uptime_seconds": int(uptime_s),
        "idle_seconds": int(idle_s),
        "threshold_seconds": threshold,
        "timestamp": now.isoformat(),
    }
    if reasons:
        response["reasons"] = reasons

    return jsonify(response), 200 if healthy else 503


@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus-style text-format metrics. Minimal scaffold — extend as needed.

    Scrape with `curl http://localhost:5050/metrics` or configure Prometheus:
        scrape_configs:
          - job_name: 'unity-bot'
            static_configs:
              - targets: ['localhost:5050']
    """
    now = datetime.utcnow()
    uptime_s = (now - _first_seen_at).total_seconds()
    idle_s = (now - _last_activity_at).total_seconds()
    bot_up = 1 if (discord_bot is not None and not discord_bot.is_closed()) else 0
    lines = [
        "# HELP unity_bot_up 1 if Discord bot is connected, 0 otherwise",
        "# TYPE unity_bot_up gauge",
        f"unity_bot_up {bot_up}",
        "# HELP unity_messages_stored Current size of the in-memory CLI bridge ring",
        "# TYPE unity_messages_stored gauge",
        f"unity_messages_stored {len(claude_messages)}",
        "# HELP unity_uptime_seconds Seconds since the Claude API process started",
        "# TYPE unity_uptime_seconds counter",
        f"unity_uptime_seconds {int(uptime_s)}",
        "# HELP unity_idle_seconds Seconds since the last recorded activity",
        "# TYPE unity_idle_seconds gauge",
        f"unity_idle_seconds {int(idle_s)}",
    ]
    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}

@app.route('/claude/read', methods=['GET'])
def read_messages():
    """Read messages from the chat history."""
    limit = request.args.get('limit', default=20, type=int)
    since = request.args.get('since', default=None, type=str)

    with messages_lock:
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                filtered = [
                    msg for msg in claude_messages
                    if datetime.fromisoformat(msg['timestamp']) > since_dt
                ]
                return jsonify({
                    "messages": filtered[-limit:],
                    "count": len(filtered[-limit:])
                })
            except ValueError as e:
                return jsonify({"error": f"Invalid timestamp format: {e}"}), 400

        return jsonify({
            "messages": claude_messages[-limit:],
            "count": len(claude_messages[-limit:])
        })

@app.route('/claude/post', methods=['POST'])
@require_admin_auth()
def post_message():
    """Post a message to the Discord channel as the authenticated admin.

    The prefix is server-derived from the admin's handle (Gee / Sponge / Red /
    Alfreddo) so Unity recognizes who's talking — clients cannot spoof identity
    via a request-body `prefix` field. Anonymous Discord/web users hit different
    surfaces and don't go through this endpoint.
    """
    if not discord_bot or discord_bot.is_closed():
        return jsonify({"error": "Discord bot not connected"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    message = data.get('message', '')
    if not message:
        return jsonify({"error": "No message provided"}), 400

    # Identity prefix is derived from the authenticated admin — NOT from the
    # request body. Format: `<Handle>: <message>` so Unity sees who's talking.
    admin = request.admin  # type: ignore[attr-defined]
    prefix = f"{admin['handle']}:"
    full_message = f"{prefix} {message}".strip()

    # Send to Discord asynchronously
    import asyncio

    async def send_discord_message():
        try:
            channel = discord_bot.get_channel(int(discord_channel_id))
            if channel:
                await channel.send(full_message)
                return True
            else:
                logger.error(f"Could not find channel {discord_channel_id}")
                return False
        except Exception as e:
            logger.error(f"Error sending message to Discord: {e}")
            return False

    # Run the async function
    try:
        loop = discord_bot.loop
        future = asyncio.run_coroutine_threadsafe(send_discord_message(), loop)
        success = future.result(timeout=10)

        if success:
            # Don't record here - bot.py on_message already records all channel messages
            return jsonify({
                "status": "sent",
                "message": full_message,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({"error": "Failed to send message"}), 500
    except Exception as e:
        logger.error(f"Error in post_message: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/claude/history', methods=['GET'])
def get_full_history():
    """Get the full message history."""
    with messages_lock:
        return jsonify({
            "messages": claude_messages,
            "count": len(claude_messages)
        })

@app.route('/claude/clear', methods=['POST'])
@require_admin_auth()
def clear_history():
    """Clear the message history (admin function)."""
    global claude_messages
    with messages_lock:
        claude_messages = []
    admin = request.admin  # type: ignore[attr-defined]
    logger.info(f"Message history cleared by admin {admin['handle']} ({admin['email']})")
    return jsonify({"status": "cleared", "cleared_by": admin["handle"]})


# ─── Admin-only endpoints — first-connect password reset + roster query ────

@app.route('/claude/admin/set-password', methods=['POST'])
@require_admin_auth(allow_force_reset=True)
def admin_set_password():
    """Set a new password for the authenticated admin + clear the reset flag.

    Only callable while the admin's force_reset flag is true (i.e., they just
    authenticated with a temp password issued by the operator). After success
    the client MUST update its UNITY_USER_PASSWORD to the new value before the
    next request — there is no session token, every call is freshly auth'd.
    """
    admin = request.admin  # type: ignore[attr-defined]
    data = request.get_json() or {}
    new_password = data.get("new_password", "")

    try:
        ok = admin_credentials.set_password(admin["email"], new_password)
    except ValueError as exc:
        return jsonify({"error": "weak_password", "message": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": "no_reset_pending", "message": str(exc)}), 403

    if not ok:
        return jsonify({"error": "unknown_admin"}), 404

    logger.info(f"Password reset completed for admin {admin['handle']} ({admin['email']})")
    return jsonify({
        "status": "password_set",
        "handle": admin["handle"],
        "force_reset": False,
        "message": "Update your client's UNITY_USER_PASSWORD env var to the new value before the next request.",
    })


@app.route('/claude/admin/whoami', methods=['GET'])
@require_admin_auth()
def admin_whoami():
    """Return the authenticated admin's identity (no password hash)."""
    admin = request.admin  # type: ignore[attr-defined]
    return jsonify({
        "email": admin["email"],
        "handle": admin["handle"],
        "alt_handles": admin.get("alt_handles", []),
        "role": admin["role"],
        "last_login": admin.get("last_login"),
    })


# Supabase /brain/* shared-knowledge proxy + CLAUDE_AUTHOR removed 2026-05-19
# per directive — V4 is single-instance only now (no claudecolab, no G/R sharing).
# See FINALIZED.md.

def run_api(port=5050, host=None):
    """Run the Flask API server.

    SECURITY.md §2.3 — default bind is `127.0.0.1` (localhost-only). Override via
    the CLAUDE_API_HOST env var or explicit `host` argument when LAN access is
    required (e.g., MCP server running on another machine). NEVER expose to the
    public internet without putting an auth layer in front.
    """
    if host is None:
        host = os.getenv("CLAUDE_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    logger.info(f"Starting Claude API on http://{host}:{port}")
    app.run(host=host, port=port, threaded=True, use_reloader=False)
