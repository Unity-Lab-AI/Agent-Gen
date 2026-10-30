#!/usr/bin/env python3
"""C.O.R.A tools: UI / modals / voice. Registered on import (see ai/tools/__init__.py)."""

import json
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.tools._base import PROJECT_DIR, Tool, _tool, _p, _ok, _err, get_tool, all_tools, tool_catalog_text

# =========================================================================== UI / modals / voice
@_tool('view_file', 'Show a file in a viewer window.', 'ui', {'path': _p('Path')}, ['path'])
def t_view_file(path: str):
    from cora_tools.modal_tools import viewfile
    return viewfile(path)


@_tool('view_code', 'Show a code file with syntax highlighting.', 'ui', {'path': _p('Path')}, ['path'])
def t_view_code(path: str):
    from cora_tools.modal_tools import viewcode
    return viewcode(path)


@_tool('view_image', 'Show an image in a window.', 'ui', {'path': _p('Path')}, ['path'])
def t_view_image(path: str):
    from cora_tools.modal_tools import viewimage
    return viewimage(path)


@_tool('show_message', 'Show a popup message to the user.', 'ui', {'text': _p('Message')}, ['text'])
def t_show_message(text: str):
    from cora_tools.modal_tools import message
    return message(text)


@_tool('stats_window', 'Open the live system stats window.', 'ui')
def t_stats_window():
    from cora_tools.modal_tools import systemstats
    return systemstats()


@_tool('monitor_panel', 'Open the monitoring panel.', 'ui')
def t_monitor_panel():
    from ui.monitor_panel import create_monitor_panel
    create_monitor_panel()
    return _ok('monitor panel open')


@_tool('open_cli_popup', 'Open the CORA terminal popup (optionally say something in it).', 'ui', {'message': _p('Text, optional')})
def t_open_cli_popup(message: str = None):
    from services.cli_popup import open_cli_popup, cli_say
    ok = open_cli_popup()
    if ok and message:
        cli_say(message)
    return _ok('terminal open') if ok else _err('could not open terminal')


@_tool('ask_user', 'Pop up a question with answer buttons and block until the user clicks one. ONLY when a task cannot '
       'continue without their decision (which file, which option). Never for conversation, greetings or small talk.', 'ui',
       {'question': _p('Question'), 'buttons': _p('Comma-separated answers, optional')}, ['question'])
def t_ask_user(question: str, buttons: str = None):
    from ui.query_panel import quick_ask
    opts = [b.strip() for b in (buttons or '').split(',') if b.strip()] or None
    ans = quick_ask(question, opts)
    return _ok(f"user answered: {ans}", answer=ans) if ans else _err('no answer')


@_tool('open_gui_app', 'Open the full CORA GUI application window (chat/tasks/knowledge/settings).', 'ui')
def t_open_gui_app():
    launcher = PROJECT_DIR / 'src' / 'gui_launcher.py'
    flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen([sys.executable, str(launcher)], cwd=str(PROJECT_DIR), creationflags=flags)
    return _ok('GUI app launching')


@_tool('what_did_you_hear', 'What CORA heard in the last 30 seconds before the wake word.', 'voice')
def t_what_did_you_hear():
    from voice.stt import WakeWordDetector
    heard = WakeWordDetector.get_last_heard()
    return _ok(heard or 'nothing caught')


@_tool('set_chattiness', 'Make CORA interject more or less on her own (ambient awareness).', 'voice',
       {'level': _p('more, less or status', enum=['more', 'less', 'status'])}, ['level'])
def t_set_chattiness(level: str):
    from voice.ambient_awareness import get_ambient_awareness
    a = get_ambient_awareness()
    if level == 'more':
        a.set_friend_threshold(min(1.0, a.friend_threshold + 0.2))
    elif level == 'less':
        a.set_friend_threshold(max(0.0, a.friend_threshold - 0.3))
    return _ok(f"friend threshold {a.friend_threshold:.0%}", status=a.get_status())


@_tool('stop_speaking', 'Stop talking immediately and drop queued speech.', 'voice')
def t_stop_speaking():
    from voice.tts import stop_speaking
    stop_speaking()
    return _ok('stopped')


@_tool('speak', 'Say something out loud right now.', 'voice', {'text': _p('Text'), 'emotion': _p('Emotion label, optional')}, ['text'])
def t_speak(text: str, emotion: str = None):
    from voice.tts import queue_speak
    queue_speak(text, emotion or 'neutral')
    return _ok('speaking')


SAY_EMOTIONS = ['neutral', 'warm', 'happy', 'amused', 'excited', 'sad', 'concerned', 'frustrated', 'surprised']
SAY_ACTS = ['statement', 'yes_no_question', 'wh_question', 'exclamation', 'instruction', 'reassurance', 'aside']


@_tool('say', "[VOICE] Say a line out loud in Unity's voice (TTS). This is how the user hears you. One to three "
       "short sentences per call; several calls for a longer reply. emotion + act are how the line is delivered; "
       "[laughter] inside the text is a real laugh.", 'voice',
       {'text': _p('What to say'),
        'emotion': _p('How it is delivered', enum=SAY_EMOTIONS),
        'act': _p('What kind of line it is', enum=SAY_ACTS)},
       ['text'])
def t_say(text: str, emotion: str = 'neutral', act: str = 'statement'):
    """The brain's trained speech tool: the designators go straight to unity-voice-v2."""
    line = str(text or '').strip()
    if not line:
        return _err('nothing to say')
    from voice.tts import queue_speak
    queue_speak(line, (emotion or 'neutral').lower(), speech_act=(act or 'statement').lower())
    return _ok(f'said: {line}', emotion=emotion, act=act)


@_tool('list_capabilities', 'List everything CORA can do (tool catalog).', 'general')
def t_list_capabilities():
    return _ok(tool_catalog_text())
