#!/usr/bin/env python3
"""
C.O.R.A conversation loop — the ONE dispatcher every entry point uses
(boot display chat, voice after the wake word, the GUI app, the CLI).

    from ai.dispatcher import get_dispatcher
    result = get_dispatcher().handle("remind me to call mom at 6", speak=True)

What it does for one user message:
  1. Control fast path ("stop", "quiet", yes/no for a pending confirmation).
  2. Builds the context: system prompt + a short dynamic block (time, mood,
     pending tasks) + the shared conversation history (ai.history).
  3. Calls the configured model with EVERY registered tool (ai.tools_registry)
     as native JSON-schema tools. Models without a tools template get the
     same tools through a JSON fallback protocol in the system prompt.
  4. Executes tool calls (destructive ones only after the user confirms),
     feeds results back, and loops until the model answers in text.
  5. Voice. Two modes (config assistant.voice_mode, 'auto' picks by model):
       say_tool - unity-brain, Unity's own LoRA: it was trained to speak by
                  calling say(text, emotion, act) with the exact designators
                  unity-voice-v2 knows, so those go straight to the voice and
                  plain reply text is screen-only (spoken with an inferred
                  delivery only if she never called say).
       stream   - any other model: tokens go to the UI and complete sentences
                  go to the voice as they arrive, emotion inferred per line.
  6. Saves the exchange to history; folds old turns into a summary when the
     context budget is tight.
"""

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ai import settings as _settings
from ai import ollama as _ollama
from ai import tools_registry as _tools
from ai.history import get_history

PROJECT_DIR = _settings.PROJECT_DIR

_STOP_WORDS = {'stop', 'quiet', 'shut up', 'be quiet', 'silence', 'mute', 'stop talking', 'shh', 'enough'}
_YES = {'yes', 'y', 'yeah', 'yep', 'do it', 'go ahead', 'confirm', 'sure', 'ok', 'okay', 'yes do it'}
_NO = {'no', 'n', 'nope', 'cancel', 'nevermind', 'never mind', 'abort', 'don\'t', 'dont'}

MAX_TOOL_ROUNDS = 6
MAX_TOOL_RESULT_CHARS = 3000

# Delivery for a line the model wrote as plain text (same rules her training
# data used to fill missing designators: Backrooms training/build_brain.py).
_DELIVERY_RULES = [
    ('sad', r"\b(died|dead|death|passed away|rip|funeral|grave|buried|miss (him|her|them)|lost (him|her))\b"),
    ('concerned', r"\b(careful|danger|injur|bleed|sick|infection|starv|low on|toxic|overdue|urgent|worried|warning)\b"),
    ('frustrated', r"\b(again|ugh|why would|seriously|every time|keeps? (doing|breaking|failing)|fuck(ing)? (this|that))\b"),
    ('surprised', r"\b(wait|what\?|whoa|no way|huh)\b"),
    ('warm', r"\b(welcome|thank|thanks|glad you|love (you|this)|appreciate|hi |hey |got you|i'm here)"),
    ('amused', r"\[laughter\]|\b(funny|lol|hilarious|ridiculous)\b"),
    ('happy', r"\b(finally|done|we did it|yes|nice|perfect|great|awesome)\b"),
]
_WH = ('what', 'where', 'why', 'how', 'who', 'which', 'when')


def infer_delivery(text: str):
    """(emotion, act) for a plain line, the way her training data inferred it."""
    low = (text or '').lower()
    emotion = next((e for e, pat in _DELIVERY_RULES if re.search(pat, low)), 'neutral')
    if '[laughter]' in low and emotion in ('neutral', 'sad', 'concerned'):
        emotion = 'amused'
    body = re.sub(r'\s*\[(laughter|breath|sigh)\]\s*', ' ', text or '').strip()
    if body.endswith('?'):
        act = 'wh_question' if body.lower().split(maxsplit=1)[0].strip(',.') in _WH else 'yes_no_question'
    elif body.endswith('!'):
        act = 'exclamation'
        emotion = 'excited' if emotion == 'neutral' else emotion
    else:
        act = 'statement'
    return emotion, act


_JSON_PROTOCOL = """
TOOL USE (this model has no native tool API): when you need a tool, reply with ONLY a JSON object on one line:
{"tool": "<name>", "arguments": {...}}
Never make up live facts: weather, time, web results, files, tasks, the screen or the camera always come from a tool call first.
Use the exact tool name from the list below.
You will get the result as the next message and can then answer the user. Available tools:
"""


def _resolve_tool_name(name: str) -> str:
    """A model on the JSON protocol (dolphin) shortens or reshapes tool names:
    'web' for web_search, 'weather' for get_weather. Snap a name that is not a
    tool to the one real tool it clearly means; leave it alone when that is unclear."""
    name = (name or '').strip()
    if not name or _tools.get_tool(name):
        return name
    names = [t.name for t in _tools.all_tools()]
    key = name.lower().replace('-', '_').replace(' ', '_')
    if key in names:
        return key
    for prefix in ('get_', 'do_', 'run_'):
        if prefix + key in names:
            return prefix + key
    hits = [n for n in names if n.startswith(key + '_') or n.endswith('_' + key)]
    if len(hits) == 1:
        return hits[0]
    import difflib
    close = difflib.get_close_matches(key, names, n=1, cutoff=0.8)
    return close[0] if close else name


def _match_tool_args(name: str, args: Dict[str, Any], selected: List[Any]) -> str:
    """The JSON-protocol model sometimes writes the right arguments on the wrong
    tool (generate_image's prompt/selfie/size on recent_images, so nothing is made).
    When the arguments do not fit the named tool but fit exactly one other tool
    (this turn's selection first, then every tool), that tool is the one she meant."""
    tool = _tools.get_tool(name)
    keys = set(args or {})
    if not tool or not keys or keys <= set(tool.params):
        return name
    for pool in (selected, _tools.all_tools()):
        fits = [t for t in pool if keys <= set(t.params) and set(t.required) <= keys]
        if len(fits) == 1:
            return fits[0].name
    return name


@dataclass
class DispatchResult:
    text: str = ''
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    spoke: bool = False
    error: Optional[str] = None
    pending_confirmation: Optional[Dict[str, Any]] = None
    elapsed: float = 0.0


class _SentenceStreamer:
    """Accumulates streamed tokens; releases complete sentences to a callback."""

    _BOUNDARY = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(\[])|(?<=[.!?])\n+|\n{2,}')

    def __init__(self, on_sentence: Callable[[str], None], min_len: int = 12):
        self.on_sentence = on_sentence
        self.min_len = min_len
        self.buf = ''

    def feed(self, token: str):
        self.buf += token
        while True:
            m = self._BOUNDARY.search(self.buf)
            if not m:
                break
            head, self.buf = self.buf[:m.start()].strip(), self.buf[m.end():]
            if len(head) >= self.min_len:
                self.on_sentence(head)
            elif head:
                self.buf = head + ' ' + self.buf

    def flush(self):
        rest = self.buf.strip()
        self.buf = ''
        if rest:
            self.on_sentence(rest)


class Dispatcher:
    def __init__(self):
        self.history = get_history()
        self._lock = threading.Lock()
        self._pending: Optional[Dict[str, Any]] = None
        self._caps_cache: Dict[str, List[str]] = {}
        self._prompt_cache: Optional[str] = None
        self.confirm_callback: Optional[Callable[[str], Optional[bool]]] = None   # UI may set: returns True/False/None(defer)

    # ------------------------------------------------------------------ prompt
    def system_prompt(self) -> str:
        if self._prompt_cache is None:
            p = PROJECT_DIR / 'config' / 'system_prompt.txt'
            try:
                self._prompt_cache = p.read_text(encoding='utf-8')
            except Exception:
                self._prompt_cache = "You are CORA, a sharp, profane, caring assistant. Stay in character."
        return self._prompt_cache

    def reload_prompt(self):
        self._prompt_cache = None

    def _assistant_config(self) -> Dict[str, Any]:
        try:
            return _settings._read_config().get('assistant') or {}
        except Exception:
            return {}

    def voice_mode(self) -> str:
        """'say_tool' (unity-brain speaks through say(text, emotion, act)) or 'stream'."""
        mode = str(self._assistant_config().get('voice_mode') or 'auto').lower()
        if mode in ('say_tool', 'stream'):
            return mode
        return 'say_tool' if _settings.chat_model().split(':')[0].startswith('unity-brain') else 'stream'

    def _dynamic_context(self) -> str:
        now = datetime.now()
        parts = [f"Now: {now.strftime('%A %B %d, %Y %I:%M %p')}."]
        try:
            who = _settings.creators()
            if who['names']:
                parts.append(f"You were made by {who['spoken']} at {who['lab']}; name all of them if asked who built you.")
        except Exception:
            pass
        try:
            from voice.emotion import get_mood
            mood = get_mood()
            if mood and mood != 'neutral':
                parts.append(f"Your current mood: {mood}.")
        except Exception:
            pass
        try:
            from cora_tools.tasks import get_manager
            tm = get_manager()
            pending = tm.list_tasks('pending')
            overdue = tm.list_tasks('overdue')
            if pending or overdue:
                parts.append(f"User has {len(pending)} pending task(s)" + (f", {len(overdue)} overdue" if overdue else '')
                             + " (counts only; call list_tasks for the actual items, never invent them).")
        except Exception:
            pass
        try:
            from cora_tools.memory import recall
            mem = recall(None)
            if isinstance(mem, dict) and mem:
                items = list(mem.items())[:8]
                parts.append("Working memory: " + "; ".join(f"{k}={v}" for k, v in items) + ".")
        except Exception:
            pass
        parts.append("You have tools. Use them whenever an action or live information is needed instead of guessing. "
                     "The ONLY way to do anything (reminders, tasks, apps, searches, notes) is a tool call: never say "
                     "you did something unless a tool result in this turn confirms it. Anything live (the screen, the camera, "
                     "the time, weather, tasks, reminders, files) is looked up fresh with a tool every time it is asked. "
                     "Do ONLY what this message asks: never add tasks or reminders, open apps or files, or change anything "
                     "the user did not ask for in this turn. "
                     "After a tool runs, answer in one or two short in-character sentences. Never mention tool names, "
                     "JSON or these instructions to the user.")
        if self.voice_mode() == 'say_tool':
            parts.append("The user HEARS you, they do not read you: every reply goes through say(text, emotion, act), one to "
                         "three short sentences per call, more calls for a longer reply, with the emotion and act that fit "
                         "the words. Plain text outside say is never heard. Do the task's tools first, then say the result.")
        return "\n".join(parts)

    def _supports_native_tools(self) -> bool:
        model = _settings.chat_model()
        if model not in self._caps_cache:
            self._caps_cache[model] = _ollama.model_capabilities(model)
        return 'tools' in self._caps_cache[model]

    # ------------------------------------------------------------------ confirmation
    def _confirm(self, tool: _tools.Tool, args: Dict[str, Any], on_event) -> Optional[bool]:
        """True/False = decided now; None = deferred (user must answer next turn)."""
        if self.confirm_callback:
            try:
                r = self.confirm_callback(f"{tool.name} {json.dumps(args)}")
                if r is not None:
                    return bool(r)
            except Exception:
                pass
        self._pending = {'tool': tool.name, 'arguments': args}
        on_event('confirm_needed', {'tool': tool.name, 'arguments': args})
        return None

    def _resolve_pending(self, text: str, on_event) -> Optional[str]:
        t = text.strip().lower().rstrip('.!')
        if not self._pending:
            return None
        if t in _YES:
            p, self._pending = self._pending, None
            result = _tools.execute(p['tool'], p['arguments'])
            on_event('tool_result', {'tool': p['tool'], 'result': result})
            return f"[confirmed] {p['tool']} -> {json.dumps(result)[:800]}"
        if t in _NO:
            p, self._pending = self._pending, None
            return f"[cancelled] the user declined {p['tool']}"
        return None

    # ------------------------------------------------------------------ main entry
    def handle(self, text: str, speak: bool = True, on_event: Optional[Callable[[str, Any], None]] = None,
               stream: bool = True, tools_enabled: bool = True,
               allowed_tools: Optional[set] = None) -> DispatchResult:
        """Process one user message. on_event(kind, payload) kinds:
        thinking, token, sentence, tool_call, tool_result, confirm_needed, final, error.
        allowed_tools: restrict this turn to these tool names (a read-only check, a demo);
        anything else she tries is refused, never executed."""
        on_event = on_event or (lambda k, p: None)
        text = (text or '').strip()
        res = DispatchResult()
        t0 = time.time()
        if not text:
            return res
        with self._lock:
            try:
                low = text.lower().rstrip('.!')
                if low in _STOP_WORDS:
                    try:
                        from voice.tts import stop_speaking
                        stop_speaking()
                    except Exception:
                        pass
                    res.text = ''
                    on_event('final', '')
                    return res

                # pending confirmation answer?
                note = self._resolve_pending(text, on_event)
                system = self.system_prompt() + "\n\n" + self._dynamic_context()
                native = tools_enabled and self._supports_native_tools()
                max_tools = int(self._assistant_config().get('max_tools', 40) or 0)
                selected = _tools.select_tools(text, max_tools) if tools_enabled else []
                if allowed_tools is not None:
                    selected = [t for t in selected if t.name in allowed_tools]
                schemas = [t.schema() for t in selected]
                if tools_enabled and not native:
                    system += _JSON_PROTOCOL + _tools.tool_catalog_text(selected)

                if self.history.needs_summary(system):
                    self.history.fold_into_summary(_ollama.summarize)

                messages = self.history.messages_for_model(system)
                user_msg = text if not note else f"{text}\n\n(system note: {note})"
                if tools_enabled and not native and selected:
                    # a small model loses the protocol 27k characters back in the persona;
                    # the rule sits next to the request instead
                    user_msg += ("\n\n(system note: if this needs live facts or an action, reply with ONLY "
                                 '{"tool": "<exact name>", "arguments": {...}} first; otherwise just answer.)')
                messages.append({'role': 'user', 'content': user_msg})

                mode = self.voice_mode()
                speaker = self._make_speaker(on_event) if (speak and mode == 'stream') else None
                said: List[str] = []
                seen_calls: set = set()                  # (name, args) already run this turn
                turn_msgs: List[Dict[str, Any]] = []     # her tool calls + results this turn, for the transcript
                final_text = ''
                for _round in range(MAX_TOOL_ROUNDS):
                    on_event('thinking', _round)
                    content, calls, err = self._call_model(messages, system, schemas if native else None,
                                                           stream, on_event, speaker if _round == 0 or True else None)
                    if err:
                        res.error = err
                        break
                    if not native and tools_enabled:
                        parsed = self._parse_json_tool(content)
                        if parsed:
                            calls, content = [parsed], ''
                    if not calls:
                        final_text = content
                        break
                    # execute tool calls
                    messages.append({'role': 'assistant', 'content': content or '',
                                     'tool_calls': [{'function': {'name': c['name'], 'arguments': c['arguments']}} for c in calls]})
                    turn_msgs.append(messages[-1])
                    deferred = False
                    for c in calls:
                        name, args = _resolve_tool_name(c['name']), c.get('arguments') or {}
                        if not native:
                            name = _match_tool_args(name, args, selected)
                        c = {**c, 'name': name}
                        res.tool_calls.append(c)
                        on_event('tool_call', {'tool': name, 'arguments': args})
                        tool = _tools.get_tool(name)
                        sig = (name, json.dumps(args, sort_keys=True, default=str))
                        if sig in seen_calls:        # the same say() text twice is never wanted either
                            result = {'ok': False, 'error': f'{name} was already called with exactly these arguments this turn; '
                                                            f'use what it returned, change the arguments, or tell the user what you found'}
                            on_event('tool_result', {'tool': name, 'result': result})
                            messages.append({'role': 'tool', 'content': json.dumps(result), 'tool_name': name})
                            turn_msgs.append(messages[-1])
                            continue
                        seen_calls.add(sig)
                        if allowed_tools is not None and name not in allowed_tools:
                            result = {'ok': False, 'error': f'{name} is not available in this session'}
                            on_event('tool_result', {'tool': name, 'result': result})
                            messages.append({'role': 'tool', 'content': json.dumps(result), 'tool_name': name})
                            turn_msgs.append(messages[-1])
                            continue
                        if name == 'say':
                            line = str(args.get('text') or '').strip()
                            if line:
                                said.append(line)
                                on_event('sentence', line)
                            result = _tools.execute(name, args) if (speak and line) else {'ok': True, 'message': f'said: {line}'}
                        elif tool and tool.confirm:
                            decision = self._confirm(tool, args, on_event)
                            if decision is None:
                                deferred = True
                                result = {'ok': False, 'pending': True,
                                          'message': f"{name} needs the user's confirmation; ask them to say yes or no."}
                            elif decision is False:
                                result = {'ok': False, 'message': 'user declined'}
                            else:
                                result = _tools.execute(name, args)
                        else:
                            result = _tools.execute(name, args)
                        on_event('tool_result', {'tool': name, 'result': result})
                        payload = json.dumps(result, default=str)
                        if len(payload) > MAX_TOOL_RESULT_CHARS:
                            payload = payload[:MAX_TOOL_RESULT_CHARS] + '..."}'
                        messages.append({'role': 'tool', 'content': payload, 'tool_name': name})
                        turn_msgs.append(messages[-1])
                    if deferred:
                        res.pending_confirmation = self._pending
                        # let the model tell the user what it wants to do
                        content, calls, err = self._call_model(messages, system, None, stream, on_event, speaker)
                        final_text = content
                        break
                else:
                    final_text = content or final_text

                if speaker:
                    speaker.flush()
                    res.spoke = True
                final_text = (final_text or '').strip()
                if not native and final_text.startswith('{'):
                    # the JSON-protocol model sometimes answers in tool-result shape; speak the words, not the JSON
                    try:
                        blob = json.loads(final_text)
                        if isinstance(blob, dict) and isinstance(blob.get('message'), str):
                            final_text = blob['message'].strip()
                    except ValueError:
                        pass
                if said:
                    res.spoke = bool(speak)
                elif mode == 'say_tool' and speak and final_text and not res.error:
                    # she answered in plain text without say(): speak it with an inferred delivery
                    try:
                        from voice.tts import queue_speak
                        e, a = infer_delivery(final_text)
                        on_event('sentence', final_text)
                        queue_speak(final_text, e, speech_act=a)
                        res.spoke = True
                    except Exception as ve:
                        on_event('error', f'voice: {ve}')
                spoken = ' '.join(said).strip()
                if not final_text:
                    shown = spoken
                elif all(line in final_text for line in said):
                    shown = final_text            # she repeated the spoken line in text; show it once
                else:
                    shown = f"{spoken} {final_text}".strip()
                res.text = shown
                if res.text:
                    self.history.add_exchange(text, res.text, turn_msgs)
                elif not res.error and res.tool_calls:
                    self.history.add_exchange(text, '(did it)', turn_msgs)
                on_event('final', res.text)
            except Exception as e:
                res.error = f"{type(e).__name__}: {e}"
                on_event('error', res.error)
        res.elapsed = time.time() - t0
        return res

    # ------------------------------------------------------------------ helpers
    def _make_speaker(self, on_event):
        def say(sentence: str):
            sentence = _ollama.scrub_placeholders(sentence)
            if not sentence.strip():
                return
            on_event('sentence', sentence)
            try:
                from voice.tts import queue_speak
                from voice.emotion import detect_emotion
                queue_speak(sentence, detect_emotion(sentence))
            except Exception as e:
                on_event('error', f"voice: {e}")
        return _SentenceStreamer(say)

    def _call_model(self, messages, system, tools, stream, on_event, speaker):
        """Returns (content, tool_calls, error)."""
        max_tokens = _settings.max_tokens()
        if stream:
            content_parts: List[str] = []
            calls: List[Dict[str, Any]] = []
            for ev in _ollama.chat_stream_events(messages, system=system, tools=tools, max_tokens=max_tokens, think=False):
                k = ev['type']
                if k == 'token':
                    content_parts.append(ev['content'])
                    on_event('token', ev['content'])
                    if speaker and not calls:
                        speaker.feed(ev['content'])
                elif k == 'tool_calls':
                    calls.extend(ev['tool_calls'])
                elif k == 'error':
                    return ''.join(content_parts), calls, ev['error']
            content = ''.join(content_parts)
            if calls and speaker:
                speaker.buf = ''     # don't speak a half-sentence that preceded a tool call
            return content, calls, None
        r = _ollama.chat(messages, system=system, tools=tools, max_tokens=max_tokens, think=False)
        if r.error:
            return '', [], r.error
        if speaker and not r.tool_calls:
            speaker.feed(r.content)
        return r.content, r.tool_calls, None

    _JSON_RE = re.compile(r'\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}', re.S)

    def _parse_json_tool(self, content: str) -> Optional[Dict[str, Any]]:
        if not content:
            return None
        m = self._JSON_RE.search(content)
        if not m:
            return None
        try:
            return {'name': m.group(1), 'arguments': json.loads(m.group(2))}
        except Exception:
            return None

    # ------------------------------------------------------------------ misc
    @property
    def pending(self) -> Optional[Dict[str, Any]]:
        return self._pending

    def cancel_pending(self):
        self._pending = None


_dispatcher: Optional[Dispatcher] = None
_dispatcher_lock = threading.Lock()


def get_dispatcher() -> Dispatcher:
    global _dispatcher
    if _dispatcher is None:
        with _dispatcher_lock:
            if _dispatcher is None:
                _dispatcher = Dispatcher()
    return _dispatcher


def ask(text: str, speak: bool = False) -> str:
    """Convenience: one message in, final text out (no streaming to a UI)."""
    r = get_dispatcher().handle(text, speak=speak, stream=False)
    return r.text if not r.error else f"[error: {r.error}]"


if __name__ == '__main__':
    import sys
    q = ' '.join(sys.argv[1:]) or "What time is it and how many tasks do I have?"
    d = get_dispatcher()
    print("native tools:", d._supports_native_tools(), "| tools:", len(_tools.all_tools()))
    r = d.handle(q, speak=False, on_event=lambda k, p: print(f"  <{k}> {str(p)[:100]}") if k != 'token' else None)
    print("RESULT:", r.text, "| calls:", [c['name'] for c in r.tool_calls], "| err:", r.error, f"| {r.elapsed:.1f}s")
