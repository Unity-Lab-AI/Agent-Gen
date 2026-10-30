#!/usr/bin/env python3
"""
C.O.R.A Ollama HTTP API Wrapper
Direct HTTP communication with Ollama.

All model names, the base URL, context size (num_ctx), keep_alive and timeouts
come from ai.settings — nothing is hardcoded here. Every request sends
options.num_ctx so Ollama never silently clips the system prompt at its 4096
default, and keep_alive so the model stays warm between turns.

Native tool calling: pass `tools=[...]` (JSON-schema tool definitions) to
chat()/chat_stream()/async_chat(); tool calls come back in
OllamaResponse.tool_calls as a list of {'name': ..., 'arguments': {...}}.
"""

import json
import asyncio
import requests
import aiohttp
from typing import Optional, Dict, Any, Generator, List, AsyncGenerator
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from ai import settings as _settings


# Backwards-compatible module constants (read-through to settings so a
# settings.reload() is honoured). Prefer the functions in ai.settings.
def _url() -> str:
    return _settings.ollama_url()


OLLAMA_BASE_URL = _settings.ollama_url()
DEFAULT_MODEL = _settings.chat_model()
VISION_MODEL = _settings.vision_model()
THINK_MODEL = _settings.think_model()
DEFAULT_TIMEOUT = _settings.timeout()


@dataclass
class OllamaResponse:
    """Structured response from Ollama API."""
    content: str
    model: str
    done: bool
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    eval_count: Optional[int] = None
    error: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    thinking: Optional[str] = None

    @property
    def ok(self) -> bool:
        return not self.error


def _error(model: str, msg: str) -> OllamaResponse:
    return OllamaResponse(content='', model=model, done=True, error=msg)


_THINK_BLOCK = None
_ANON_SELF = None
_ANON_TAG = None


def scrub_placeholders(text: str) -> str:
    """dolphin3 was trained on text anonymized with Presidio and writes the
    placeholder itself (<PRESIDIOANONYMIZEDPERSON> for 'CORA', for 'Aurora').
    'I'm <tag>' is her name; any other tag is dropped."""
    global _ANON_SELF, _ANON_TAG
    if not text or 'PRESIDIO' not in text:
        return text
    import re
    if _ANON_TAG is None:
        _ANON_SELF = re.compile(r"\b(I'm|I am|call me|my name is|it's|this is)\s+<PRESIDIOANONYMIZED[A-Z_]*>", re.I)
        _ANON_TAG = re.compile(r'\s*<PRESIDIOANONYMIZED[A-Z_]*>')
    text = _ANON_SELF.sub(lambda m: m.group(1) + ' CORA', text)
    return _ANON_TAG.sub('', text)


def _clean_think(text: str) -> str:
    """Thinking is off on every call, but the Qwen family still emits a stray
    `</think>` now and then (seen on a camera description: the answer, then the
    tag, then invented text). A whole <think>...</think> block is dropped; a lone
    closing tag keeps the side that carries the answer."""
    global _THINK_BLOCK
    text = scrub_placeholders(text)
    if not text or 'think>' not in text:
        return text
    import re
    if _THINK_BLOCK is None:
        _THINK_BLOCK = re.compile(r'<think>.*?</think>', re.S)
    text = _THINK_BLOCK.sub('', text)
    if '</think>' in text:
        before, after = text.split('</think>', 1)
        text = before if len(before.strip()) >= 20 else after
    return text.replace('<think>', '').strip()


def _parse_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalise Ollama's message.tool_calls into [{'name', 'arguments'}]."""
    calls = []
    for tc in message.get('tool_calls') or []:
        fn = tc.get('function') or {}
        args = fn.get('arguments')
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {'_raw': args}
        calls.append({'name': fn.get('name', ''), 'arguments': args or {}})
    return calls


def _chat_payload(messages, model, system, temperature, max_tokens, tools, stream, think):
    msgs = list(messages)
    if system:
        msgs = [{'role': 'system', 'content': system}] + msgs
    payload: Dict[str, Any] = {
        'model': model,
        'messages': msgs,
        'stream': stream,
        'keep_alive': _settings.keep_alive(),
        'options': _settings.base_options(temperature, max_tokens, model),
    }
    if tools:
        payload['tools'] = tools
    if think is not None:
        payload['think'] = bool(think)
    return payload


def _response_from_chat_json(data: Dict[str, Any], model: str) -> OllamaResponse:
    message = data.get('message', {}) or {}
    return OllamaResponse(
        content=_clean_think(message.get('content', '') or ''),
        model=data.get('model', model),
        done=data.get('done', True),
        total_duration=data.get('total_duration'),
        load_duration=data.get('load_duration'),
        prompt_eval_count=data.get('prompt_eval_count'),
        eval_count=data.get('eval_count'),
        tool_calls=_parse_tool_calls(message),
        thinking=message.get('thinking'),
    )


# ============ STATUS / MODEL MANAGEMENT ============

def check_ollama() -> Dict[str, Any]:
    """Check if Ollama is running and get status.

    Returns:
        Dict with 'connected', 'models', 'model_names', 'error' keys
    """
    try:
        resp = requests.get(f"{_url()}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('models', [])
            return {
                'connected': True,
                'models': len(models),
                'model_names': [m.get('name', '') for m in models],
                'error': None
            }
        return {'connected': False, 'models': 0, 'model_names': [],
                'error': f'HTTP {resp.status_code}'}
    except requests.ConnectionError:
        return {'connected': False, 'models': 0, 'model_names': [],
                'error': 'Ollama not running. Start with: ollama serve'}
    except requests.Timeout:
        return {'connected': False, 'models': 0, 'model_names': [],
                'error': 'Ollama connection timeout'}
    except Exception as e:
        return {'connected': False, 'models': 0, 'model_names': [], 'error': str(e)}


def list_models() -> List[Dict[str, Any]]:
    """List all available Ollama models."""
    try:
        resp = requests.get(f"{_url()}/api/tags", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [{
                'name': m.get('name', ''),
                'size': m.get('size', 0),
                'modified': m.get('modified_at', ''),
                'digest': (m.get('digest', '') or '')[:12]
            } for m in data.get('models', [])]
    except Exception:
        pass
    return []


def has_model(name: str) -> bool:
    """True if a model (exact tag, or base name with any tag) is pulled."""
    names = [m['name'] for m in list_models()]
    if name in names:
        return True
    base = name.split(':')[0]
    return any(n.split(':')[0] == base for n in names)


def pull_model(model_name: str, callback: Optional[callable] = None) -> bool:
    """Pull/download a model from the Ollama library."""
    try:
        resp = requests.post(f"{_url()}/api/pull", json={'name': model_name},
                             stream=True, timeout=600)
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                if callback:
                    callback(data.get('status', ''), data.get('completed', 0), data.get('total', 0))
                if data.get('status') == 'success':
                    return True
        return resp.status_code == 200
    except Exception as e:
        if callback:
            callback(f'Error: {e}', 0, 0)
        return False


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a model (/api/show)."""
    try:
        resp = requests.post(f"{_url()}/api/show", json={'name': model_name}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def model_capabilities(model_name: str) -> List[str]:
    """Capabilities Ollama reports for a model, e.g. ['completion', 'tools', 'vision']."""
    info = get_model_info(model_name) or {}
    return list(info.get('capabilities') or [])


def delete_model(model_name: str) -> bool:
    """Delete a model from Ollama."""
    try:
        resp = requests.delete(f"{_url()}/api/delete", json={'name': model_name}, timeout=30)
        return resp.status_code == 200
    except Exception:
        return False


def create_model(name: str, modelfile: str, callback: Optional[callable] = None) -> bool:
    """Create a custom model from a Modelfile."""
    try:
        resp = requests.post(f"{_url()}/api/create", json={'name': name, 'modelfile': modelfile},
                             stream=True, timeout=300)
        for line in resp.iter_lines():
            if line:
                data = json.loads(line)
                if callback:
                    callback(data.get('status', ''))
                if data.get('status') == 'success':
                    return True
        return resp.status_code == 200
    except Exception:
        return False


def loaded_models(timeout: int = 5) -> List[str]:
    """Names of the models Ollama currently holds in memory (GPU)."""
    try:
        resp = requests.get(f"{_url()}/api/ps", timeout=timeout)
        return [m.get('name', '') for m in resp.json().get('models', []) if m.get('name')] if resp.ok else []
    except Exception:
        return []


def unload_models(names: Optional[List[str]] = None, timeout: int = 15) -> List[str]:
    """Release the GPU: keep_alive 0 for every loaded model (or the given names).
    Called on every normal CORA exit and by the stop scripts; returns what was unloaded."""
    done = []
    for name in (names or loaded_models()):
        try:
            requests.post(f"{_url()}/api/generate", json={'model': name, 'keep_alive': 0}, timeout=timeout)
            done.append(name)
        except Exception:
            pass
    if names is None:
        # her image engine leaves the GPU with her brain (the sidecar she started is stopped)
        try:
            from cora_tools.image_gen import release as _release_image
            state = _release_image()
            if state in ('stopped', 'unloaded'):
                done.append(f'image engine ({state})')
        except Exception:
            pass
    return done


def warm_up(model: Optional[str] = None, timeout: int = 180) -> bool:
    """Load a model into memory with the configured num_ctx so the first real
    request is not a cold start. Returns True when the model is resident."""
    model = model or _settings.chat_model()
    try:
        resp = requests.post(f"{_url()}/api/chat", json={
            'model': model, 'messages': [], 'stream': False,
            'keep_alive': _settings.keep_alive(),
            'options': {'num_ctx': _settings.num_ctx(model)},
        }, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


# ============ CHAT ============

def chat(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    think: Optional[bool] = False,
) -> OllamaResponse:
    """Send a chat completion request (non-streaming).

    Args:
        messages: [{'role': 'user'|'assistant'|'tool', 'content': '...'}]; a
                  user message may carry 'images': [base64, ...]
        model: Model name (default: settings chat model)
        system: Optional system prompt
        temperature: Sampling temperature (default from settings)
        max_tokens: Max response tokens (num_predict)
        timeout: Request timeout in seconds (default from settings)
        tools: JSON-schema tool definitions for native tool calling
        think: Force thinking on/off for models that support it

    Returns:
        OllamaResponse with content, tool_calls and metadata
    """
    model = model or _settings.chat_model()
    timeout = timeout or _settings.timeout()
    try:
        payload = _chat_payload(messages, model, system, temperature, max_tokens, tools, False, think)
        resp = requests.post(f"{_url()}/api/chat", json=payload, timeout=timeout)
        if resp.status_code == 200:
            return _response_from_chat_json(resp.json(), model)
        return _error(model, f"HTTP {resp.status_code}: {resp.text}")
    except requests.ConnectionError:
        return _error(model, 'Ollama not running. Start with: ollama serve')
    except requests.Timeout:
        return _error(model, 'Request timeout - model may be loading')
    except Exception as e:
        return _error(model, str(e))


def chat_stream(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    think: Optional[bool] = False,
) -> Generator[str, None, None]:
    """Streaming chat completion. Yields content tokens as they arrive.

    If the model answers with tool calls instead of text, the generator yields
    a single string starting with '[tool_calls]' followed by the JSON list, so
    callers that stream can still detect tool use. Prefer chat_stream_events()
    for structured handling.
    """
    for event in chat_stream_events(messages, model, system, temperature, max_tokens, timeout, tools, think):
        if event['type'] == 'token':
            yield event['content']
        elif event['type'] == 'tool_calls':
            yield '[tool_calls]' + json.dumps(event['tool_calls'])
        elif event['type'] == 'error':
            yield f"[Error: {event['error']}]"


def chat_stream_events(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    think: Optional[bool] = False,
) -> Generator[Dict[str, Any], None, None]:
    """Streaming chat that yields structured events:
        {'type': 'token', 'content': str}
        {'type': 'tool_calls', 'tool_calls': [...]}
        {'type': 'done', 'response': OllamaResponse}
        {'type': 'error', 'error': str}
    """
    model = model or _settings.chat_model()
    timeout = timeout or _settings.timeout()
    full = []
    calls: List[Dict[str, Any]] = []
    last: Dict[str, Any] = {}
    try:
        payload = _chat_payload(messages, model, system, temperature, max_tokens, tools, True, think)
        resp = requests.post(f"{_url()}/api/chat", json=payload, stream=True, timeout=timeout)
        if resp.status_code != 200:
            yield {'type': 'error', 'error': f"HTTP {resp.status_code}: {resp.text[:200]}"}
            return
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            last = data
            message = data.get('message', {}) or {}
            content = message.get('content', '')
            if content:
                full.append(content)
                yield {'type': 'token', 'content': content}
            tc = _parse_tool_calls(message)
            if tc:
                calls.extend(tc)
                yield {'type': 'tool_calls', 'tool_calls': tc}
            if data.get('done', False):
                break
        final = OllamaResponse(
            content=_clean_think(''.join(full)), model=last.get('model', model), done=True,
            total_duration=last.get('total_duration'), load_duration=last.get('load_duration'),
            prompt_eval_count=last.get('prompt_eval_count'), eval_count=last.get('eval_count'),
            tool_calls=calls)
        yield {'type': 'done', 'response': final}
    except requests.ConnectionError:
        yield {'type': 'error', 'error': 'Ollama not running'}
    except requests.Timeout:
        yield {'type': 'error', 'error': 'Request timeout'}
    except Exception as e:
        yield {'type': 'error', 'error': str(e)}


def generate(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    raw: bool = False,
    timeout: Optional[int] = None
) -> OllamaResponse:
    """Generate completion for a single prompt (non-chat)."""
    model = model or _settings.chat_model()
    timeout = timeout or _settings.timeout()
    try:
        payload = {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'raw': raw,
            'think': False,
            'keep_alive': _settings.keep_alive(),
            'options': _settings.base_options(temperature, max_tokens, model),
        }
        if system:
            payload['system'] = system
        resp = requests.post(f"{_url()}/api/generate", json=payload, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            return OllamaResponse(
                content=_clean_think(data.get('response', '')),
                model=data.get('model', model),
                done=data.get('done', True),
                total_duration=data.get('total_duration'),
                load_duration=data.get('load_duration'),
                prompt_eval_count=data.get('prompt_eval_count'),
                eval_count=data.get('eval_count')
            )
        return _error(model, f"HTTP {resp.status_code}: {resp.text}")
    except requests.ConnectionError:
        return _error(model, 'Ollama not running')
    except requests.Timeout:
        return _error(model, 'Request timeout - model may be loading')
    except Exception as e:
        return _error(model, str(e))


# ============ VISION (Image Analysis) ============

def _encode_image(image_path: str) -> Optional[str]:
    import base64
    from pathlib import Path
    p = Path(image_path)
    if not p.exists():
        return None
    with open(p, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def generate_with_image(
    prompt: str,
    image_path: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 200,
    timeout: Optional[int] = None
) -> OllamaResponse:
    """Describe/answer a question about an image using the vision model."""
    model = model or _settings.vision_model()
    timeout = timeout or _settings.vision_timeout()
    image_data = _encode_image(image_path)
    if image_data is None:
        return _error(model, f"Image not found: {image_path}")
    messages = [{'role': 'user', 'content': prompt, 'images': [image_data]}]
    return chat(messages, model=model, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout)


def analyze_image(image_path: str, prompt: str = "Describe what you see in this image.",
                  model: Optional[str] = None, timeout: Optional[int] = None) -> str:
    """Convenience wrapper: returns the description text or '' on error."""
    r = generate_with_image(prompt, image_path, model=model, timeout=timeout)
    return '' if r.error else r.content.strip()


# ============ CONVENIENCE ============

def quick_ask(question: str, model: Optional[str] = None) -> str:
    """Quick single-turn question."""
    response = chat(messages=[{'role': 'user', 'content': question}], model=model)
    if response.error:
        return f"[Error: {response.error}]"
    return response.content


def summarize(text: str, model: Optional[str] = None) -> str:
    """Summarize text (convenience wrapper)."""
    return quick_ask(f"Summarize this concisely:\n\n{text}", model=model)


# ============ THINK (quick local decisions) ============

def think(
    prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 100,
    temperature: float = 0.3,
    timeout: Optional[int] = None
) -> str:
    """Quick local AI for simple internal decisions. Returns '' on error."""
    try:
        response = generate(prompt=prompt, model=model or _settings.think_model(),
                            max_tokens=max_tokens, temperature=temperature,
                            timeout=timeout or _settings.think_timeout())
        if response.error:
            return ""
        return response.content.strip()
    except Exception:
        return ""


def think_bool(prompt: str, model: Optional[str] = None) -> bool:
    """Quick yes/no decision using local AI."""
    response = think(f"Answer only 'yes' or 'no': {prompt}", model=model, max_tokens=10).lower()
    return response.startswith('yes') or 'true' in response


def think_choice(prompt: str, choices: list, model: Optional[str] = None) -> str:
    """Quick multiple choice decision using local AI."""
    choice_str = ', '.join(choices)
    response = think(f"{prompt}\nChoose ONLY ONE from: {choice_str}\nAnswer with just the choice:",
                     model=model, max_tokens=20).strip().lower()
    for choice in choices:
        if choice.lower() in response or response in choice.lower():
            return choice
    return choices[0] if choices else ""


def think_classify(text: str, categories: list, model: Optional[str] = None) -> str:
    """Classify text into one of the categories."""
    return think_choice(f"Classify this text: '{text}'", categories, model=model)


def think_extract(text: str, what: str, model: Optional[str] = None) -> str:
    """Extract specific information from text."""
    return think(f"Extract the {what} from this text. Return ONLY the {what}, nothing else:\n{text}",
                 model=model, max_tokens=50)


# ============ ASYNC VERSIONS ============

_executor = ThreadPoolExecutor(max_workers=3)


async def async_check_ollama() -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, check_ollama)


async def async_list_models() -> List[Dict[str, Any]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, list_models)


async def async_chat(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    think: Optional[bool] = False,
) -> OllamaResponse:
    """Async non-blocking chat completion using aiohttp."""
    model = model or _settings.chat_model()
    timeout = timeout or _settings.timeout()
    try:
        payload = _chat_payload(messages, model, system, temperature, max_tokens, tools, False, think)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{_url()}/api/chat", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return _response_from_chat_json(await resp.json(), model)
                return _error(model, f"HTTP {resp.status}: {await resp.text()}")
    except aiohttp.ClientConnectorError:
        return _error(model, 'Ollama not running. Start with: ollama serve')
    except asyncio.TimeoutError:
        return _error(model, 'Request timeout - model may be loading')
    except Exception as e:
        return _error(model, str(e))


async def async_chat_stream(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    think: Optional[bool] = False,
) -> AsyncGenerator[str, None]:
    """Async streaming chat completion. Yields content tokens."""
    model = model or _settings.chat_model()
    timeout = timeout or _settings.timeout()
    try:
        payload = _chat_payload(messages, model, system, temperature, max_tokens, tools, True, think)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{_url()}/api/chat", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    yield f"[Error: HTTP {resp.status}]"
                    return
                async for line in resp.content:
                    if not line:
                        continue
                    data = json.loads(line.decode('utf-8'))
                    message = data.get('message', {}) or {}
                    content = message.get('content', '')
                    if content:
                        yield content
                    tc = _parse_tool_calls(message)
                    if tc:
                        yield '[tool_calls]' + json.dumps(tc)
                    if data.get('done', False):
                        break
    except aiohttp.ClientConnectorError:
        yield "[Error: Ollama not running]"
    except asyncio.TimeoutError:
        yield "[Error: Request timeout]"
    except Exception as e:
        yield f"[Error: {e}]"


async def async_generate(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None
) -> OllamaResponse:
    """Async generate completion for a single prompt."""
    model = model or _settings.chat_model()
    timeout = timeout or _settings.timeout()
    try:
        payload = {
            'model': model, 'prompt': prompt, 'stream': False, 'think': False,
            'keep_alive': _settings.keep_alive(),
            'options': _settings.base_options(temperature, max_tokens, model),
        }
        if system:
            payload['system'] = system
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{_url()}/api/generate", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return OllamaResponse(
                        content=data.get('response', ''), model=data.get('model', model),
                        done=data.get('done', True), total_duration=data.get('total_duration'),
                        load_duration=data.get('load_duration'),
                        prompt_eval_count=data.get('prompt_eval_count'),
                        eval_count=data.get('eval_count'))
                return _error(model, f"HTTP {resp.status}: {await resp.text()}")
    except aiohttp.ClientConnectorError:
        return _error(model, 'Ollama not running')
    except Exception as e:
        return _error(model, str(e))


async def async_think(prompt: str, model: Optional[str] = None, max_tokens: int = 100,
                      temperature: float = 0.3, timeout: Optional[int] = None) -> str:
    """Async version of think()."""
    try:
        response = await async_generate(prompt=prompt, model=model or _settings.think_model(),
                                        max_tokens=max_tokens, temperature=temperature,
                                        timeout=timeout or _settings.think_timeout())
        return "" if response.error else response.content.strip()
    except Exception:
        return ""


async def async_quick_ask(question: str, model: Optional[str] = None) -> str:
    """Async quick single-turn question."""
    response = await async_chat(messages=[{'role': 'user', 'content': question}], model=model)
    if response.error:
        return f"[Error: {response.error}]"
    return response.content


if __name__ == "__main__":
    print("=== OLLAMA API TEST ===")
    print(f"URL: {_url()}  chat={_settings.chat_model()}  vision={_settings.vision_model()}  "
          f"num_ctx={_settings.num_ctx()}")
    status = check_ollama()
    print(f"Connected: {status['connected']}  Models: {status['models']}")
    if status['model_names']:
        print(f"Available: {', '.join(status['model_names'][:8])}")
    if status['error']:
        print(f"Error: {status['error']}")
    if status['connected']:
        print(f"Capabilities of {_settings.chat_model()}: {model_capabilities(_settings.chat_model())}")
        response = chat([{'role': 'user', 'content': "Say 'Hello from CORA!' in exactly 5 words."}])
        print(f"Response: {response.content!r}  error={response.error}")
