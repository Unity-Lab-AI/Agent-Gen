#!/usr/bin/env python3
"""
C.O.R.A tools registry (facade).

The tools moved into the ai/tools/ package on 2026-10-14 (one module per
category, each under 800 lines); this module keeps the import path everything
uses and re-exports the same names:

    from ai.tools_registry import execute, select_tools, all_tools, tool_schemas, _tool, _p, _ok, _err
"""
from ai.tools import *  # noqa: F401,F403
from ai.tools import (PROJECT_DIR, Tool, _REGISTRY, register_tool, get_tool, all_tools, tool_schemas,  # noqa: F401
                      tool_catalog_text, _p, _ok, _err, _tool, CORE_TOOLS, select_tools, execute,
                      SAY_EMOTIONS, SAY_ACTS)
from ai.tools.tasks import _normalize_due  # noqa: F401
from ai.tools.calendar import _parse_when  # noqa: F401
