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

# Split into the cora_tools.code_parts package on 2026-10-14; this module keeps every name it always had.
from cora_tools.code_parts import _base  # noqa: F401
from cora_tools.code_parts._base import Any, CodeAnalysis, CodeResult, Dict, Enum, HAS_OLLAMA, Language, List, Optional, Path, Tuple, _code_assistant, analyze_code, chat, dataclass, detect_language, explain_code, fix_code, get_code_assistant, os, re, run_code, subprocess, sys, tempfile, think, write_code  # noqa: F401
from cora_tools.code_parts.assistant import CodeAssistant  # noqa: F401




# Module test
if __name__ == '__main__':
    print("=== CODE ASSISTANT TEST ===\n")

    print(f"Ollama available: {HAS_OLLAMA}")

    assistant = get_code_assistant()

    # Test language detection
    test_code = '''
def hello(name):
    """Say hello."""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    hello("World")
'''

    print("\n--- Language Detection ---")
    lang = assistant.detect_language(test_code)
    print(f"Detected: {lang}")

    print("\n--- Static Explanation ---")
    explanation = assistant._static_explain(test_code, lang)
    print(explanation)

    print("\n--- Code Execution ---")
    result = assistant.run_code(test_code)
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    if result.error:
        print(f"Error: {result.error}")

    # Test dangerous code detection
    print("\n--- Safety Check ---")
    dangerous = "import os; os.remove('/important/file')"
    is_dangerous = assistant._is_dangerous(dangerous, "python")
    print(f"Dangerous code detected: {is_dangerous}")

    print("\n=== TEST COMPLETE ===")
