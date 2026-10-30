#!/usr/bin/env python3
"""C.O.R.A tools: vision + images. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== vision + images
@_tool('take_screenshot', 'Capture the desktop and LOOK at it: returns what is on screen (app, site, what the user is doing). '
       'Ask a specific question to look for something in particular.', 'vision',
       {'question': _p('What to look for on the screen (optional)'),
        'describe': _p('false = just save the file without looking', 'boolean')})
def t_take_screenshot(question: str = None, describe: bool = True):
    from cora_tools.screenshots import desktop
    r = desktop()
    if not r.success:
        return _err(r.error or 'screenshot failed')
    out = {'path': str(r.path), 'size': f"{r.width}x{r.height}"}
    if describe or question:
        from ai.ollama import generate_with_image
        q = question or ('Describe what is on this screen in two sentences: which application or site is open and '
                         'what the user is doing. Be concrete, read visible titles and text.')
        v = generate_with_image(q, str(r.path), max_tokens=220)
        out['description'] = v.content.strip() if not v.error else f"vision error: {v.error}"
        return _ok(out['description'], **out)
    return _ok(f"Screenshot saved to {r.path}", **out)


@_tool('look_camera', 'Look through the webcam and describe/answer a question about what is visible.', 'vision',
       {'question': _p('Question about the view, optional')})
def t_look_camera(question: str = None):
    from services.presence import capture_webcam, ask_vision
    p = capture_webcam()
    if not p:
        return _err('camera unavailable')
    desc = ask_vision(p, question or 'Describe what you see in detail: people, objects, environment, mood.')
    return _ok(desc or 'vision returned nothing', path=str(p))


@_tool('check_presence', 'Is someone at the desk? Includes emotion/activity when visible.', 'vision')
def t_check_presence():
    from services.presence import full_human_check
    r = full_human_check()
    if r.error:
        return _err(r.error)
    return _ok('present' if r.present else 'nobody there', present=r.present, emotion=r.emotion,
               activity=r.activity, posture=r.posture, holding=r.holding)


@_tool('open_camera', 'Open the live webcam window.', 'vision')
def t_open_camera():
    from ui.camera_feed import open_live_camera
    cam = open_live_camera()
    return _ok('camera window open') if cam else _err('could not open camera')


@_tool('close_camera', 'Close the live webcam window.', 'vision')
def t_close_camera():
    from ui.camera_feed import close_live_camera
    close_live_camera()
    return _ok('camera closed')


@_tool('generate_image', 'Make a picture from a description on her own local image engine (no internet). The picture '
       'opens in a window with Save As and Open folder; call save_image to put it somewhere the user names. '
       'Use for: image, picture, photo, selfie, art, drawing, scene, wallpaper.', 'images',
       {'prompt': _p('Detailed description of the picture: subject, setting, lighting, style. For a selfie: only the '
                      'moment (where you are, pose, expression, light); your look is added automatically'),
        'selfie': _p('true when the picture is of CORA herself (selfie, "picture of you"): her look comes from '
                     'config so she is the same girl every time', 'boolean'),
        'width': _p('Pixels, 256-1024 (default 768; landscape 1024x576, portrait 576x1024)', 'integer'),
        'height': _p('Pixels, 256-1024', 'integer'),
        'show': _p('Open the result in the viewer window (default true)', 'boolean')}, ['prompt'])
def t_generate_image(prompt: str, selfie: bool = False, width: int = None, height: int = None, show: bool = True):
    from cora_tools.image_gen import generate_image, show_image
    import re as _re
    if not selfie and _re.search(r'\b(selfie|of me|myself|picture of you|photo of you|pic of you|cora)\b', (prompt or '').lower()):
        selfie = True
    r = generate_image(prompt, selfie=bool(selfie), width=int(width) if width else None, height=int(height) if height else None)
    if not r.get('success'):
        return _err(r.get('error', 'generation failed'))
    if show:
        show_image(r['path'], caption=prompt)
    return _ok(f"Picture made in {r.get('inference_time', 0):.1f}s and shown in a window (Save As / Open folder there); "
               f"saved at {r['path']}", path=r['path'], seed=r.get('seed'), engine=r.get('engine'),
               width=r.get('width'), height=r.get('height'))


@_tool('edit_image', 'Change an existing picture with words (img2img on her local engine): restyle it, change the '
       'weather, the colors, what someone wears, add or remove things. source = a file path, "last" (the newest '
       'picture she made) or "camera" (a fresh webcam shot). strength 0.3 keeps almost everything, 0.55 is a '
       'real edit, 0.8 keeps only the layout. Give a box to repaint only that region.', 'images',
       {'source': _p('File path, "last" or "camera"'),
        'prompt': _p('What the picture should become / what goes in the box'),
        'strength': _p('0.2-0.95, default 0.55', 'number'),
        'box': _p('Optional region to repaint, [x0, y0, x1, y1] as fractions 0-1 of the image', 'array'),
        'keep_face': _p('Lock the face of the person in the source (default false; true for people)', 'boolean'),
        'show': _p('Open the result in the viewer window (default true)', 'boolean')}, ['source', 'prompt'])
def t_edit_image(source: str, prompt: str, strength: float = 0.55, box=None, keep_face: bool = False, show: bool = True):
    from cora_tools.image_gen import edit_image, show_image
    try:
        box_list = [float(v) for v in box] if box else None
    except (TypeError, ValueError):
        return _err('box must be four numbers [x0, y0, x1, y1] between 0 and 1')
    r = edit_image(source, prompt, strength=float(strength or 0.55), box=box_list, keep_face=bool(keep_face))
    if not r.get('success'):
        return _err(r.get('error', 'edit failed'))
    if show:
        show_image(r['path'], caption=f"edit: {prompt}")
    return _ok(f"Edited in {r.get('inference_time', 0):.1f}s, shown in a window; saved at {r['path']}",
               path=r['path'], source=r.get('source'), seed=r.get('seed'))


@_tool('recreate_camera', 'Take a webcam shot and recreate it through her local image engine: the same scene and '
       'person repainted as the prompt says (a painting, a cyberpunk version, a different outfit, a '
       'different place) with the face kept. Use when the user wants a picture OF themselves or their room '
       'made into something.', 'images',
       {'prompt': _p('What to turn the shot into (empty = the same scene, painted realistically)'),
        'strength': _p('0.3 subtle ... 0.8 only the layout stays, default 0.6', 'number'),
        'keep_face': _p('Keep the face of whoever is on camera (default true)', 'boolean'),
        'show': _p('Open the result in the viewer window (default true)', 'boolean')})
def t_recreate_camera(prompt: str = '', strength: float = 0.6, keep_face: bool = True, show: bool = True):
    from cora_tools.image_gen import recreate_camera, show_image
    r = recreate_camera(prompt or '', strength=float(strength or 0.6), keep_face=bool(keep_face))
    if not r.get('success'):
        return _err(r.get('error', 'camera recreation failed'))
    if show:
        show_image(r['path'], caption=f"camera recreation: {prompt or 'the same scene'}")
    return _ok(f"Camera shot recreated in {r.get('inference_time', 0):.1f}s, shown in a window; saved at {r['path']}",
               path=r['path'], source=r.get('source'), seed=r.get('seed'))


@_tool('save_image', 'Save a picture where the user asks: a folder (Desktop, Pictures, D:/art) or a full file '
       'name. source = "last" (the newest picture she made or edited, default), a file path, or "camera" for a '
       'fresh webcam shot.', 'images',
       {'destination': _p('Folder or file path; ~ and relative paths are fine (relative = under the home folder)'),
        'source': _p('"last" (default), a file path, or "camera"')}, ['destination'])
def t_save_image(destination: str, source: str = 'last'):
    from cora_tools.image_gen import save_image
    r = save_image(destination, source or 'last')
    if not r.get('success'):
        return _err(r.get('error', 'save failed'))
    return _ok(f"Saved to {r['path']}", path=r['path'], source=r.get('source'))


@_tool('show_image', 'Open a picture in her viewer window (Save As, Open folder, Copy path). path = a file, '
       '"last" for the newest picture, or "camera" for a fresh webcam shot.', 'images',
       {'path': _p('File path, "last" or "camera"'), 'caption': _p('Optional caption')})
def t_show_image(path: str = 'last', caption: str = None):
    from cora_tools.image_gen import show_image, _resolve_source
    try:
        p = _resolve_source(path or 'last')
    except Exception as e:
        return _err(str(e))
    return _ok(f"Shown: {p}", path=str(p)) if show_image(p, caption=caption) else _err('could not open the viewer')


@_tool('recent_images', 'List recently generated or edited images (newest first).', 'images',
       {'limit': _p('How many', 'integer')})
def t_recent_images(limit: int = 5):
    from cora_tools.image_gen import get_recent_images
    return _ok('images', images=get_recent_images(int(limit or 5)))
