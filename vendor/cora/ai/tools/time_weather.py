#!/usr/bin/env python3
"""C.O.R.A tools: time / weather / location. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== time / weather / location
@_tool('get_time', 'Current local time and date.', 'time')
def t_get_time():
    now = datetime.now()
    return _ok(f"It's {now.strftime('%I:%M %p').lstrip('0')} on {now.strftime('%A, %B %d, %Y')}",
               time=now.strftime('%H:%M'), date=now.strftime('%Y-%m-%d'), weekday=now.strftime('%A'))


@_tool('get_weather', 'Current weather (city optional, defaults to the user\'s location).', 'time',
       {'location': _p('City name, optional')})
def t_get_weather(location: str = None):
    from services.weather import get_weather
    w = get_weather(location or None)
    if not w or not w.get('success'):
        return _err('weather unavailable')
    return _ok(f"{w.get('temp')} and {w.get('conditions')}", **{k: v for k, v in w.items() if k != 'success'})


@_tool('get_forecast', 'Multi-day weather forecast.', 'time',
       {'location': _p('City name, optional'), 'days': _p('Number of days (1-5)', 'integer')})
def t_get_forecast(location: str = None, days: int = 3):
    from services.weather import get_forecast
    f = get_forecast(location or None, days=int(days or 3))
    if not f or not f.get('success'):
        return _err('forecast unavailable')
    return _ok('forecast', forecast=f.get('forecast'))


@_tool('get_location', 'Where the user is (city/region/country from IP).', 'time')
def t_get_location():
    from services.location import get_location, format_location_string
    loc = get_location()
    return _ok(format_location_string(loc), **(loc or {})) if loc else _err('location unavailable')
