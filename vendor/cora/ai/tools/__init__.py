#!/usr/bin/env python3
"""
C.O.R.A tools package: importing it registers every tool.

    from ai.tools import execute, select_tools, all_tools   # or via ai.tools_registry
"""
from ai.tools._base import (PROJECT_DIR, Tool, _REGISTRY, register_tool, get_tool, all_tools, tool_schemas,
                            tool_catalog_text, _p, _ok, _err, _tool, CORE_TOOLS, select_tools, execute)
from ai.tools import time_weather as _time_weather  # noqa: F401,E402
from ai.tools import tasks as _tasks  # noqa: F401,E402
from ai.tools import knowledge as _knowledge  # noqa: F401,E402
from ai.tools import calendar as _calendar  # noqa: F401,E402
from ai.tools import vision as _vision  # noqa: F401,E402
from ai.tools import web as _web  # noqa: F401,E402
from ai.tools import files as _files  # noqa: F401,E402
from ai.tools import system as _system  # noqa: F401,E402
from ai.tools import windows as _windows  # noqa: F401,E402
from ai.tools import code as _code  # noqa: F401,E402
from ai.tools import media as _media  # noqa: F401,E402
from ai.tools import git as _git  # noqa: F401,E402
from ai.tools import email as _email  # noqa: F401,E402
from ai.tools import self_modify as _self_modify  # noqa: F401,E402
from ai.tools import ui_voice as _ui_voice  # noqa: F401,E402
from ai.tools.ui_voice import SAY_EMOTIONS, SAY_ACTS  # noqa: E402

__all__ = ['PROJECT_DIR', 'Tool', 'register_tool', 'get_tool', 'all_tools', 'tool_schemas', 'tool_catalog_text',
           'CORE_TOOLS', 'select_tools', 'execute', 'SAY_EMOTIONS', 'SAY_ACTS']
