#!/usr/bin/env python3
"""
UnityBotV4 — Web Server
=========================

A standalone Flask app that serves:
  - GET  /                 → web/index.html (single-page app: setup wizard + chat UI)
  - GET  /api/state        → {configured, pollinations_stack, model_default, ...}
  - POST /api/setup        → validate + write .env
  - GET  /api/models       → list available Pollinations models
  - POST /api/chat         → chat completion (text + image URLs)
  - POST /api/image        → direct image generation
  - GET  /api/health       → health check

Run modes:
  - Standalone:   `python web_server.py`   (no Discord, just the web UI)
  - Combined:    `python bot.py` running alongside (web on :5051, bot on Discord)

Cross-platform — pure Python + Flask, no build pipeline. Works in any browser
on Linux + Windows. Default bind: 127.0.0.1:5051. Use --host 0.0.0.0 for LAN.

Usage:
    python web_server.py                          # localhost:5051
    python web_server.py --host 0.0.0.0           # bind all interfaces
    python web_server.py --port 8080              # custom port
    python web_server.py --no-browser             # don't auto-open browser
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import re
import signal
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS


SCRIPT_DIR = Path(__file__).resolve().parent
WEB_DIR = SCRIPT_DIR / "web"
ENV_PATH = SCRIPT_DIR / ".env"
IMAGES_DIR = SCRIPT_DIR / "generated_images"

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="/web")
CORS(app)


# ─── State ──────────────────────────────────────────────────────────────────

# Lazy Config + APIClient — loaded once .env is configured. Reset to None
# during setup so we can validate-then-reload.
_config = None
_api_client = None
_aiohttp_session = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_event_loop_thread: Optional[threading.Thread] = None
# Lock guards _load_config() against concurrent reloads (MEDIUM #11).
# Without it two simultaneous /api/setup calls could race-create two Configs
# and leak the old aiohttp ClientSession.
_config_lock = threading.Lock()


def _start_event_loop_thread() -> None:
    """Start a dedicated asyncio loop in a background thread for async API calls."""
    global _event_loop, _event_loop_thread

    if _event_loop is not None:
        return

    ready = threading.Event()

    def runner():
        global _event_loop
        loop = asyncio.new_event_loop()
        _event_loop = loop
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    _event_loop_thread = threading.Thread(target=runner, daemon=True, name="web-asyncio")
    _event_loop_thread.start()
    ready.wait(timeout=5)


def run_async(coro):
    """Submit a coroutine to the background event loop and wait for its result."""
    if _event_loop is None:
        _start_event_loop_thread()
    future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
    return future.result(timeout=120)


def _load_config():
    """Attempt to load Config from current env. Returns Config instance or None if not yet configured.

    Thread-safe via _config_lock (MEDIUM #11). Properly closes the previous
    APIClient's aiohttp ClientSession before replacing it, preventing the
    file-descriptor leak that previously occurred on every reload.
    """
    global _config, _api_client

    with _config_lock:
        # Re-read .env so changes via /api/setup are picked up
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_PATH, override=True)
        except ImportError:
            pass

        try:
            if "config" in sys.modules:
                import importlib
                import config as _config_mod
                importlib.reload(_config_mod)
            from config import Config
            from api_client import APIClient
        except ImportError as e:
            logger.error(f"Failed to import config/api_client: {e}")
            return None

        try:
            cfg = Config()
        except (ValueError, FileNotFoundError) as e:
            logger.info(f"Config not yet valid: {e}")
            return None

        # Stash the OLD client so we can close it AFTER the new one is wired in
        old_client = _api_client

        _config = cfg
        _api_client = APIClient(cfg)
        _start_event_loop_thread()
        run_async(_api_client.initialize())

        # Drain the old aiohttp ClientSession to release sockets
        if old_client is not None and old_client is not _api_client:
            try:
                run_async(old_client.close())
            except Exception as e:
                logger.warning(f"Couldn't close old APIClient cleanly: {e}")

        return cfg


def _signal_bot_reload() -> bool:
    """Send SIGHUP to bot.py if its PID file is present, triggering hot-reload
    of config + api_client on the Discord side (closes MEDIUM #10).

    Returns True if SIGHUP was sent, False if no PID file / not POSIX / kill failed.
    No-op on Windows (no SIGHUP — operator must restart bot.py).
    """
    pid_file = SCRIPT_DIR / "logs" / "bot.pid"
    if not pid_file.exists():
        return False
    if not hasattr(signal, "SIGHUP"):
        logger.info("SIGHUP not supported on this platform — bot must be restarted to pick up changes")
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGHUP)
        logger.info(f"Sent SIGHUP to bot.py (PID {pid}) — Discord side will hot-reload config")
        return True
    except (ValueError, ProcessLookupError, PermissionError) as e:
        logger.warning(f"Couldn't SIGHUP bot.py: {e}")
        return False


def is_configured() -> bool:
    return _config is not None


# ─── Setup validation ───────────────────────────────────────────────────────

DISCORD_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{50,100}$")
POLLINATIONS_PK_RE = re.compile(r"^pk_[A-Za-z0-9]{8,64}$")
POLLINATIONS_SK_RE = re.compile(r"^sk_[A-Za-z0-9]{8,64}$")
POLLINATIONS_LEGACY_RE = re.compile(r"^[A-Za-z0-9]{16}$")
CHANNEL_ID_LIST_RE = re.compile(r"^(\d{15,25})(,\d{15,25})*$")
PORT_RE = re.compile(r"^\d{1,5}$")


def validate_field(key: str, value: str) -> tuple[bool, str]:
    if value == "":
        # Empty is OK for optional fields — caller decides which are required
        return True, ""
    if key == "DISCORD_TOKEN":
        if DISCORD_TOKEN_RE.match(value):
            return True, ""
        return False, "Expected 50-100 chars (A-Z, a-z, 0-9, . _ -). Token may have been copied with extra whitespace or wrapping quotes."
    if key == "POLLINATIONS_API_KEY":
        if POLLINATIONS_PK_RE.match(value):
            return True, "publishable (pk_) key — client-side safe, rate-limited"
        if POLLINATIONS_SK_RE.match(value):
            return True, "secret (sk_) key — server-side only, no rate limits"
        return False, "Expected pk_xxx (publishable) or sk_xxx (secret) from https://enter.pollinations.ai"
    if key == "POLLINATIONS_TOKEN":
        if POLLINATIONS_LEGACY_RE.match(value):
            return True, "legacy 16-char token — still supported as fallback"
        return False, "Expected exactly 16 alphanumeric chars (legacy format). Use POLLINATIONS_API_KEY for new pk_/sk_ keys."
    if key in ("CLAUDE_CHAT_CHANNEL_ID",):
        if re.match(r"^\d{15,25}$", value):
            return True, ""
        return False, "Expected a 15-25 digit numeric Discord channel ID."
    if key == "CLAUDE_API_PORT":
        if PORT_RE.match(value) and 1 <= int(value) <= 65535:
            return True, ""
        return False, "Expected a port number between 1 and 65535."
    if key in ("ALLOWED_CHANNELS",):
        if CHANNEL_ID_LIST_RE.match(value):
            return True, f"{len(value.split(','))} channel(s) allowlisted"
        return False, "Expected comma-separated channel IDs (no spaces), e.g. 1234567890,9876543210"
    if key == "ALLOWED_GUILDS":
        # Allow no-dms token mixed in
        parts = [p.strip() for p in value.split(",") if p.strip()]
        for p in parts:
            if p == "no-dms":
                continue
            if not re.match(r"^\d{15,25}$", p):
                return False, f"Invalid entry: '{p}'. Expected 15-25 digit guild IDs (or special token 'no-dms')."
        return True, f"{len([p for p in parts if p != 'no-dms'])} guild(s) approved" + (", DMs disabled" if "no-dms" in parts else "")
    if key == "ALLOWED_GUILDS_STRICT":
        if value in ("1", "0", "true", "false", "yes", "no"):
            return True, ""
        return False, "Expected 1, 0, or empty."
    # Collab subsystem validators (CLAUDE_AUTHOR / CLAUDE_COLLAB_KEY /
    # SUPABASE_*) removed 2026-05-19 — V4 is single-instance only.
    # Unknown field — accept as-is
    return True, ""


# ─── .env I/O ───────────────────────────────────────────────────────────────

def read_env() -> dict[str, str]:
    result: dict[str, str] = {}
    if not ENV_PATH.exists():
        return result
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def write_env(values: dict[str, str]) -> None:
    sections = [
        ("Required — Discord", ["DISCORD_TOKEN"]),
        ("Required — Pollinations.AI (new gen.pollinations.ai stack)",
            ["POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN"]),
        ("Optional — Claude CLI bridge", ["CLAUDE_CHAT_CHANNEL_ID", "CLAUDE_API_PORT", "CLAUDE_API_HOST"]),
        ("Optional — Guild allowlist (approved Discord servers)",
            ["ALLOWED_GUILDS", "ALLOWED_GUILDS_STRICT", "ALLOWED_CHANNELS"]),
        ("Optional — Web UI (browser-based chat + setup wizard)",
            ["WEB_UI_ENABLED", "WEB_UI_HOST", "WEB_UI_PORT"]),
        ("Optional — Observability",
            ["HEALTHZ_IDLE_THRESHOLD_SECONDS"]),
        ("Optional — Auto-update", ["DISABLE_AUTOUPDATE"]),
        # Collab subsystem section removed 2026-05-19 — V4 is single-instance only.
    ]
    lines = [
        "# UnityBotV4 — environment configuration",
        f"# Written by web_server.py at {datetime.now().isoformat(timespec='seconds')}",
        "# Format: KEY=value  (no quotes, no surrounding spaces)",
        "",
    ]
    known: set[str] = set()
    for title, keys in sections:
        lines.append(f"# ─── {title} ───")
        for k in keys:
            known.add(k)
            v = values.get(k, "")
            if v:
                lines.append(f"{k}={v}")
            else:
                lines.append(f"# {k}=")
        lines.append("")
    extras = [k for k in values if k not in known]
    if extras:
        lines.append("# ─── Custom (preserved from existing .env) ───")
        for k in extras:
            lines.append(f"{k}={values[k]}")
        lines.append("")
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the single-page app."""
    return send_from_directory(str(WEB_DIR), "index.html")


@app.route("/api/state", methods=["GET"])
def api_state():
    """Tell the SPA whether setup is needed or chat is ready."""
    configured = is_configured()
    state = {
        "configured": configured,
        "env_exists": ENV_PATH.exists(),
        "env_values_preview": {},
    }
    # Surface a non-secret preview of current values
    values = read_env()
    secret_keys = {"DISCORD_TOKEN", "POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN",
                   "UNITY_USER_PASSWORD"}
    for k, v in values.items():
        if v and k in secret_keys:
            state["env_values_preview"][k] = v[:6] + "…" + (v[-4:] if len(v) > 12 else "")
        else:
            state["env_values_preview"][k] = v
    if configured:
        state["pollinations_stack"] = _config.pollinations_stack
        state["chat_url"] = _config.chat_url
        state["image_base"] = _config.image_base
        state["default_model"] = _config.default_model
    return jsonify(state)


@app.route("/api/setup/validate", methods=["POST"])
def api_setup_validate():
    """Validate a single field (live as the user types)."""
    data = request.get_json(force=True) or {}
    key = data.get("key", "")
    value = data.get("value", "")
    ok, note = validate_field(key, value)
    return jsonify({"valid": ok, "note": note})


@app.route("/api/setup", methods=["POST"])
def api_setup():
    """Receive the complete form, validate required fields, write .env."""
    data = request.get_json(force=True) or {}
    fields = data.get("fields", {})

    # Required: DISCORD_TOKEN + (POLLINATIONS_API_KEY OR POLLINATIONS_TOKEN)
    errors: dict[str, str] = {}
    if not fields.get("DISCORD_TOKEN"):
        errors["DISCORD_TOKEN"] = "Required."
    elif not validate_field("DISCORD_TOKEN", fields["DISCORD_TOKEN"])[0]:
        errors["DISCORD_TOKEN"] = validate_field("DISCORD_TOKEN", fields["DISCORD_TOKEN"])[1]

    poll_api = fields.get("POLLINATIONS_API_KEY", "")
    poll_legacy = fields.get("POLLINATIONS_TOKEN", "")
    if not (poll_api or poll_legacy):
        errors["POLLINATIONS_API_KEY"] = "Required (or use legacy POLLINATIONS_TOKEN)."
    elif poll_api and not validate_field("POLLINATIONS_API_KEY", poll_api)[0]:
        errors["POLLINATIONS_API_KEY"] = validate_field("POLLINATIONS_API_KEY", poll_api)[1]
    elif poll_legacy and not validate_field("POLLINATIONS_TOKEN", poll_legacy)[0]:
        errors["POLLINATIONS_TOKEN"] = validate_field("POLLINATIONS_TOKEN", poll_legacy)[1]

    # Validate optional fields that are set
    for k, v in fields.items():
        if k in ("DISCORD_TOKEN", "POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN"):
            continue
        if not v:
            continue
        ok, note = validate_field(k, v)
        if not ok:
            errors[k] = note

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # Merge with existing values to preserve unknown keys
    existing = read_env()
    existing.update({k: v for k, v in fields.items() if v})
    # Remove keys explicitly cleared (sent as empty when previously set)
    for k, v in fields.items():
        if v == "" and k in existing:
            del existing[k]

    write_env(existing)

    # Reload config — if the new env is valid, chat becomes available
    cfg = _load_config()
    # Also nudge bot.py to hot-reload via SIGHUP (POSIX only — no-op on Windows)
    bot_reloaded = _signal_bot_reload()
    return jsonify({
        "ok": True,
        "configured": cfg is not None,
        "bot_reloaded": bot_reloaded,
        "message": (
            "Configuration saved. Web UI reloaded."
            + (" Discord bot reloaded via SIGHUP." if bot_reloaded else " (Discord bot restart needed to pick up changes.)")
            if cfg else "Saved but config still invalid — check error logs."
        ),
    })


@app.route("/api/models", methods=["GET"])
def api_models():
    """List available Pollinations text-generation models."""
    if not is_configured():
        return jsonify({"error": "Not configured yet"}), 503
    try:
        models = run_async(_api_client.fetch_models())
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e), "models": []}), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Send a chat turn. Returns text + image URLs."""
    if not is_configured():
        return jsonify({"error": "Not configured yet"}), 503

    _web_touch_activity()
    data = request.get_json(force=True) or {}
    user_text = data.get("message", "").strip()
    history = data.get("history", [])
    model = data.get("model") or _config.default_model

    if not user_text:
        return jsonify({"error": "Empty message"}), 400

    system_prompt = f"{_config.system_instructions}\nYou are {model}."
    messages = [{"role": "system", "content": system_prompt}]
    # Map UI history → API messages (user/assistant)
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    try:
        response = run_async(_api_client.send_message(messages, model))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if isinstance(response, str) and response.startswith("Error:"):
        return jsonify({"error": response}), 502

    # Clean prefixes + extract image URLs
    text = re.sub(r"^\s*\[(?:claude|revclaude|gpt|openai|assistant)\]\s*:?\s*", "", response, flags=re.IGNORECASE).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text_lines = [
        line for line in text.split("\n")
        if not re.match(r"^---", line) and "Generated by" not in line and not re.search(r"\d{4}-\d{2}-\d{2}", line)
    ]
    text = "\n".join(text_lines).strip()
    image_urls = re.findall(r"https?://\S+", text)
    text_without_urls = re.sub(r"https?://\S+", "", text).strip()

    return jsonify({
        "text": text_without_urls,
        "image_urls": image_urls,
        "model": model,
    })


@app.route("/api/image", methods=["POST"])
def api_image():
    """Direct image generation (bypass chat)."""
    if not is_configured():
        return jsonify({"error": "Not configured yet"}), 503

    data = request.get_json(force=True) or {}
    prompt = data.get("prompt", "").strip()
    model = data.get("model", "flux")
    width = int(data.get("width", 1024))
    height = int(data.get("height", 1024))
    seed = data.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            seed = None

    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    url = _config.image_url(prompt, model=model, width=width, height=height, seed=seed)
    return jsonify({"url": url, "prompt": prompt, "model": model, "width": width, "height": height, "seed": seed})


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "configured": is_configured(),
        "timestamp": datetime.utcnow().isoformat(),
    })


# ─── Parity with claude_api: /healthz + /metrics on web_server too ─────────

_web_first_seen_at = datetime.utcnow()
_web_last_activity_at = datetime.utcnow()


def _web_touch_activity():
    global _web_last_activity_at
    _web_last_activity_at = datetime.utcnow()


@app.route("/healthz", methods=["GET"])
def healthz():
    """Health check matching claude_api's schema (closes LOW #14 — parity).

    Returns 200 when configured + active, 503 when not-configured OR idle.
    Threshold configurable via HEALTHZ_IDLE_THRESHOLD_SECONDS (default 600s).
    """
    now = datetime.utcnow()
    uptime_s = (now - _web_first_seen_at).total_seconds()
    idle_s = (now - _web_last_activity_at).total_seconds()
    threshold = int(os.getenv("HEALTHZ_IDLE_THRESHOLD_SECONDS", "600"))
    configured = is_configured()
    healthy = True
    reasons = []
    if not configured:
        healthy = False
        reasons.append("not configured (set DISCORD_TOKEN + POLLINATIONS_API_KEY)")
    if uptime_s > threshold and idle_s > threshold:
        healthy = False
        reasons.append(f"no activity in {int(idle_s)}s (threshold={threshold}s)")
    resp = {
        "healthy": healthy,
        "configured": configured,
        "uptime_seconds": int(uptime_s),
        "idle_seconds": int(idle_s),
        "threshold_seconds": threshold,
        "timestamp": now.isoformat(),
    }
    if reasons:
        resp["reasons"] = reasons
    return jsonify(resp), 200 if healthy else 503


@app.route("/metrics", methods=["GET"])
def web_metrics():
    """Prometheus-style metrics for the web UI side (closes LOW #14)."""
    now = datetime.utcnow()
    uptime_s = (now - _web_first_seen_at).total_seconds()
    idle_s = (now - _web_last_activity_at).total_seconds()
    configured = 1 if is_configured() else 0
    lines = [
        "# HELP unity_web_configured 1 if .env has valid keys, 0 otherwise",
        "# TYPE unity_web_configured gauge",
        f"unity_web_configured {configured}",
        "# HELP unity_web_uptime_seconds Seconds since web_server started",
        "# TYPE unity_web_uptime_seconds counter",
        f"unity_web_uptime_seconds {int(uptime_s)}",
        "# HELP unity_web_idle_seconds Seconds since last chat or setup activity",
        "# TYPE unity_web_idle_seconds gauge",
        f"unity_web_idle_seconds {int(idle_s)}",
    ]
    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"}


@app.route("/web/<path:path>")
def web_static(path):
    return send_from_directory(str(WEB_DIR), path)


# ─── Entrypoint ─────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="UnityBotV4 web UI server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1 — use 0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=5051, help="Bind port (default: 5051)")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open the browser on startup")
    parser.add_argument("--debug", action="store_true", help="Flask debug mode")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not WEB_DIR.exists():
        print(f"  ! ERROR: {WEB_DIR} not found — the web UI files are missing")
        return 1
    if not (WEB_DIR / "index.html").exists():
        print(f"  ! ERROR: {WEB_DIR / 'index.html'} missing")
        return 1

    # Try to load config now — if .env is already valid, chat is ready immediately
    _load_config()

    print("=" * 60)
    print("UnityBotV4 — Web UI")
    print("=" * 60)
    print(f"  bind:        {args.host}:{args.port}")
    print(f"  web dir:     {WEB_DIR}")
    print(f"  .env exists: {ENV_PATH.exists()}")
    print(f"  configured:  {is_configured()}")
    print()
    url = f"http://{'localhost' if args.host == '0.0.0.0' else args.host}:{args.port}/"
    print(f"  Open in browser: {url}")
    if not is_configured():
        print(f"  (.env is not yet valid — the page will start in setup-wizard mode)")
    print("=" * 60)

    if not args.no_browser:
        # Defer slightly so Flask is up before the browser hits it
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
