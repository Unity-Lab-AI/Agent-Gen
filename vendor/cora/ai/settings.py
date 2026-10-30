#!/usr/bin/env python3
"""
C.O.R.A AI/runtime settings — the ONE place model names, Ollama URL, context
size and timeouts come from.

Precedence (highest first):
  1. Environment variables  (OLLAMA_URL / OLLAMA_HOST, CORA_CHAT_MODEL, ...)
  2. config/config.json     ("ollama" and "models" blocks)
  3. Built-in defaults below

Every module that talks to Ollama imports from here instead of hardcoding a
model name or URL. Call reload() after editing config.json at runtime.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / 'config' / 'config.json'

# Built-in defaults — overridden by config.json / env. Chosen 2026-10-14:
# unity-brain is Unity's own text LoRA (Qwen3.5-9B, Backrooms/models/unity-brain):
# it calls say(text, emotion, act) with the designators unity-voice-v2 was
# trained on and reads images itself, so it is chat + vision. The chat model
# doubles as the code model. huihui_ai/qwen3-abliterated:8b is the fallback.
_DEFAULTS: Dict[str, Any] = {
    'ollama_url': 'http://127.0.0.1:11434',
    'chat_model': 'unity-brain',
    'vision_model': 'unity-brain',
    'code_model': None,          # None -> chat_model
    'think_model': None,         # None -> chat_model
    'num_ctx': 16384,            # Ollama silently clips at 4096 if unset
    'keep_alive': '30m',         # keep the model warm between turns
    'timeout': 120,              # seconds for a full chat completion
    'think_timeout': 30,
    'vision_timeout': 90,
    'temperature': 0.7,
    'max_tokens': 500,
    'history_turns': 40,         # user+assistant messages kept in context
}

# Per-model request options (context + sampling). Keyed by model name or the
# part before ':'. config.json "models.options" adds/overrides entries.
# unity-brain (her own LoRA, Backrooms/models/unity-brain) ships these in its
# Modelfile and MUST always get the same num_ctx (32768): a request with a
# different context makes Ollama reload it with a huge default (~14 GB).
_MODEL_OPTIONS: Dict[str, Dict[str, Any]] = {
    # temperature/presence are calmer than her stream Modelfile (1.0 / 1.5): at those
    # values she skips tool calls and riffs on stale answers; 0.7 / 1.0 keep the voice
    'unity-brain': {'num_ctx': 32768, 'temperature': 0.7, 'top_k': 20, 'top_p': 0.95, 'presence_penalty': 1.0},
}

_cache: Optional[Dict[str, Any]] = None


def _read_config() -> Dict[str, Any]:
    try:
        from ai import config as _config
        return _config.load()
    except Exception:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}


def _normalize_url(url: str) -> str:
    url = (url or '').strip().rstrip('/')
    if not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    return url


def _build() -> Dict[str, Any]:
    cfg = _read_config()
    ollama = cfg.get('ollama', {}) or {}
    models = cfg.get('models', {}) or {}
    ai = cfg.get('ai', {}) or {}

    s = dict(_DEFAULTS)

    # config.json
    if ollama.get('api_url'):
        s['ollama_url'] = _normalize_url(ollama['api_url'])
    for key in ('num_ctx', 'keep_alive', 'timeout', 'think_timeout', 'vision_timeout'):
        if ollama.get(key) is not None:
            s[key] = ollama[key]
    if models.get('primary'):
        s['chat_model'] = models['primary']
    elif ollama.get('model'):
        s['chat_model'] = ollama['model']
    for key in ('vision', 'code', 'think'):
        if models.get(key):
            s[key + '_model'] = models[key]
    for key in ('temperature', 'max_tokens', 'history_turns'):
        if ai.get(key) is not None:
            s[key] = ai[key]

    # environment
    env_url = os.environ.get('OLLAMA_URL') or os.environ.get('OLLAMA_HOST')
    if env_url:
        s['ollama_url'] = _normalize_url(env_url)
    for env, key in (('CORA_CHAT_MODEL', 'chat_model'), ('CORA_VISION_MODEL', 'vision_model'),
                     ('CORA_CODE_MODEL', 'code_model'), ('CORA_THINK_MODEL', 'think_model')):
        if os.environ.get(env):
            s[key] = os.environ[env]
    if os.environ.get('CORA_NUM_CTX'):
        try:
            s['num_ctx'] = int(os.environ['CORA_NUM_CTX'])
        except ValueError:
            pass

    s['model_options'] = {k: dict(v) for k, v in _MODEL_OPTIONS.items()}
    for name, opts in (models.get('options') or {}).items():
        if isinstance(opts, dict):
            s['model_options'][name] = {**s['model_options'].get(name, {}), **opts}

    if not s['code_model']:
        s['code_model'] = s['chat_model']
    if not s['think_model']:
        s['think_model'] = s['chat_model']
    return s


def settings() -> Dict[str, Any]:
    """Cached settings dict."""
    global _cache
    if _cache is None:
        _cache = _build()
    return _cache


def reload() -> Dict[str, Any]:
    """Re-read config.json and the environment."""
    global _cache
    _cache = _build()
    return _cache


# Accessors — read-through so a reload() is picked up everywhere.
def ollama_url() -> str:
    return settings()['ollama_url']


def chat_model() -> str:
    return settings()['chat_model']


def vision_model() -> str:
    return settings()['vision_model']


def code_model() -> str:
    return settings()['code_model']


def think_model() -> str:
    return settings()['think_model']


def model_options(model: Optional[str] = None) -> Dict[str, Any]:
    """Request options pinned to one model (exact name, name before ':', or prefix)."""
    model = model or chat_model()
    opts = settings().get('model_options') or {}
    if model in opts:
        return dict(opts[model])
    base = model.split(':')[0]
    if base in opts:
        return dict(opts[base])
    for key, val in opts.items():
        if model.startswith(key):
            return dict(val)
    return {}


def num_ctx(model: Optional[str] = None) -> int:
    """Context size for a model (its pinned value if it has one, else the global one)."""
    return int(model_options(model).get('num_ctx', settings()['num_ctx']))


def keep_alive() -> str:
    return str(settings()['keep_alive'])


def timeout() -> int:
    return int(settings()['timeout'])


def think_timeout() -> int:
    return int(settings()['think_timeout'])


def vision_timeout() -> int:
    return int(settings()['vision_timeout'])


def temperature() -> float:
    return float(settings()['temperature'])


def max_tokens() -> int:
    return int(settings()['max_tokens'])


def history_turns() -> int:
    return int(settings()['history_turns'])


def creators() -> Dict[str, Any]:
    """Who made her, from config.json (the block holding a "creators" list):
    {'lab': 'Unity AI Lab', 'names': [...], 'roles': {name: role}, 'spoken': 'A, B, C, and D'}."""
    cfg = _read_config()
    block = next((v for v in cfg.values() if isinstance(v, dict) and isinstance(v.get('creators'), list)), {})
    names, roles = [], {}
    for c in block.get('creators') or []:
        if isinstance(c, dict) and c.get('name'):
            names.append(str(c['name']))
            if c.get('role'):
                roles[str(c['name'])] = str(c['role'])
        elif isinstance(c, str):
            names.append(c)
    spoken = ', '.join(names[:-1]) + (', and ' if len(names) > 2 else ' and ' if len(names) == 2 else '') + names[-1] if names else ''
    return {'lab': str(block.get('name') or 'Unity AI Lab'), 'names': names, 'roles': roles, 'spoken': spoken}


def base_options(temperature_override: Optional[float] = None,
                 max_tokens_override: Optional[int] = None,
                 model: Optional[str] = None) -> Dict[str, Any]:
    """The options block every Ollama request should carry (per-model pins win
    over the global temperature; an explicit override wins over both)."""
    pinned = model_options(model)
    temp = pinned.get('temperature', settings()['temperature'])
    opts: Dict[str, Any] = {
        'temperature': temp if temperature_override is None else temperature_override,
        'num_ctx': num_ctx(model),
    }
    for key in ('top_k', 'top_p', 'min_p', 'presence_penalty', 'repeat_penalty'):
        if key in pinned:
            opts[key] = pinned[key]
    mt = max_tokens_override if max_tokens_override is not None else None
    if mt:
        # think_tokens: headroom for models that reason before answering even with
        # think off (qwen3-vl): without it the whole budget goes to thinking and the
        # answer comes back empty
        opts['num_predict'] = int(mt) + int(pinned.get('think_tokens', 0) or 0)
    return opts


if __name__ == '__main__':
    for k, v in settings().items():
        print(f"{k:16} = {v}")
