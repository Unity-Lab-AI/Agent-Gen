#!/usr/bin/env python3
"""Shared base of the cora_tools.code_parts package (split from cora_tools/code.py on 2026-10-14): imports, module
state, the helpers and every function that rebinds a module global."""
from __future__ import annotations
#!/usr/bin/env python3
"""
C.O.R.A Code Assistance Tools
AI-powered code explanation, writing, fixing, and execution.

Per ARCHITECTURE.md v1.0.0:
- explain_code(code)
- write_code(description)
- fix_code(code, error)
- run_code(code)

Created by: Unity AI Lab
Date: 2025-12-23
"""

import subprocess
import tempfile
import os
import sys
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from ai.ollama import chat, think
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    chat = None
    think = None


class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    BASH = "bash"
    POWERSHELL = "powershell"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    SQL = "sql"
    UNKNOWN = "unknown"


@dataclass
class CodeResult:
    """Result of code execution."""
    success: bool
    output: str
    error: str
    return_code: int
    language: str


@dataclass
class CodeAnalysis:
    """Analysis of code."""
    language: str
    summary: str
    explanation: str
    issues: List[str]
    suggestions: List[str]


# Global instance
_code_assistant: Optional[CodeAssistant] = None


def get_code_assistant(model: str = None) -> CodeAssistant:
    from cora_tools.code_parts.assistant import CodeAssistant
    """Get or create the global CodeAssistant instance."""
    global _code_assistant
    if _code_assistant is None:
        _code_assistant = CodeAssistant(model=model)
    return _code_assistant


# Convenience functions (per ARCHITECTURE.md spec)
def explain_code(code: str, detail_level: str = "medium") -> str:
    """Explain what code does."""
    result = get_code_assistant().explain_code(code, detail_level)

    # Show in modal
    try:
        from ui.modals import show_code_modal, show_modal_threadsafe
        lang = get_code_assistant().detect_language(code)
        show_modal_threadsafe(show_code_modal, code, "", lang, f"Code Explanation ({lang})")
    except Exception:
        pass

    return result


def write_code(description: str, language: str = "python") -> str:
    """Generate code from description."""
    result = get_code_assistant().write_code(description, language)

    # Show generated code in modal
    try:
        from ui.modals import show_code_modal, show_modal_threadsafe
        show_modal_threadsafe(show_code_modal, result, "", language, f"Generated Code ({language})")
    except Exception:
        pass

    return result


def fix_code(code: str, error: Optional[str] = None) -> str:
    """Fix errors in code."""
    result = get_code_assistant().fix_code(code, error)

    # Show fixed code in modal
    try:
        from ui.modals import show_code_modal, show_modal_threadsafe
        lang = get_code_assistant().detect_language(code)
        show_modal_threadsafe(show_code_modal, result, "", lang, f"Fixed Code ({lang})")
    except Exception:
        pass

    return result


def run_code(code: str, language: Optional[str] = None, safe_mode: bool = True) -> CodeResult:
    """Execute code and return results."""
    result = get_code_assistant().run_code(code, language, safe_mode=safe_mode)

    # Show output in terminal modal
    try:
        from ui.modals import show_terminal_modal, show_modal_threadsafe
        output = result.output if result.output else result.error
        status = "Success" if result.success else "Failed"
        show_modal_threadsafe(show_terminal_modal, output, f"[{result.language}] {status}", "Code Execution")
    except Exception:
        pass

    return result


def analyze_code(code: str) -> CodeAnalysis:
    """Analyze code for issues and suggestions."""
    result = get_code_assistant().analyze_code(code)

    # Show analysis in modal
    try:
        from ui.modals import show_code_modal, show_modal_threadsafe
        analysis_text = f"# Code Analysis\n\n"
        analysis_text += f"## Summary\n{result.summary}\n\n"
        analysis_text += f"## Explanation\n{result.explanation}\n\n"
        if result.issues:
            analysis_text += f"## Issues\n" + "\n".join(f"- {i}" for i in result.issues) + "\n\n"
        if result.suggestions:
            analysis_text += f"## Suggestions\n" + "\n".join(f"- {s}" for s in result.suggestions)
        show_modal_threadsafe(show_code_modal, analysis_text, "", "markdown", f"Code Analysis ({result.language})")
    except Exception:
        pass

    return result


def detect_language(code: str) -> str:
    """Detect programming language from code."""
    return get_code_assistant().detect_language(code)
