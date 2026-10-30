#!/usr/bin/env python3
"""cora_tools.code_parts: assistant (split from cora_tools/code.py on 2026-10-14)."""
from __future__ import annotations

import subprocess
import tempfile
import os
import sys
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
from cora_tools.code_parts import _base  # noqa: F401
from cora_tools.code_parts._base import CodeAnalysis, CodeResult, HAS_OLLAMA, Language, Optional, Path, analyze_code, chat, detect_language, explain_code, fix_code, re, run_code, subprocess, sys, tempfile, write_code  # noqa: F401




class CodeAssistant:
    """
    AI-powered code assistance.

    Provides functions to explain, write, fix, and run code.
    Uses local Ollama models for AI operations.
    """

    # Coding model: config/config.json models.code, else the chat model (ai.settings)
    @staticmethod
    def default_model() -> str:
        try:
            from ai.settings import code_model
            return code_model()
        except Exception:
            return "unity-brain"

    def __init__(self, model: str = None, timeout: int = 60):
        """Initialize code assistant.

        Args:
            model: Ollama model to use for code tasks (defaults to models.code / the chat model)
            timeout: Timeout for AI operations in seconds
        """
        self.model = model or self.default_model()
        self.timeout = timeout
        self._temp_dir = Path(tempfile.gettempdir()) / "cora_code"
        self._temp_dir.mkdir(exist_ok=True)

    def detect_language(self, code: str) -> str:
        """Detect programming language from code.

        Args:
            code: Source code

        Returns:
            Language name string
        """
        code_lower = code.lower().strip()

        # Python indicators
        if any(x in code for x in ['def ', 'import ', 'from ', 'class ', 'print(', 'if __name__']):
            return Language.PYTHON.value
        if code.startswith('#!') and 'python' in code_lower[:50]:
            return Language.PYTHON.value

        # JavaScript indicators
        if any(x in code for x in ['function ', 'const ', 'let ', 'var ', '=>', 'console.log']):
            return Language.JAVASCRIPT.value
        if 'document.' in code or 'window.' in code:
            return Language.JAVASCRIPT.value

        # Bash indicators
        if code.startswith('#!/bin/bash') or code.startswith('#!/bin/sh'):
            return Language.BASH.value
        if any(x in code for x in ['echo ', '| grep', 'if [', 'for i in']):
            return Language.BASH.value

        # PowerShell indicators
        if any(x in code for x in ['$PSVersionTable', 'Write-Host', 'Get-', 'Set-', '-eq', '-ne']):
            return Language.POWERSHELL.value

        # HTML indicators
        if '<html' in code_lower or '<!doctype' in code_lower or '<div' in code_lower:
            return Language.HTML.value

        # CSS indicators
        if '{' in code and (':' in code) and (';' in code):
            if any(x in code_lower for x in ['color:', 'margin:', 'padding:', 'display:', 'font-']):
                return Language.CSS.value

        # JSON indicators
        if code.strip().startswith('{') and code.strip().endswith('}'):
            try:
                import json
                json.loads(code)
                return Language.JSON.value
            except Exception:
                pass

        # SQL indicators
        if any(x in code_lower for x in ['select ', 'insert ', 'update ', 'delete ', 'create table']):
            return Language.SQL.value

        return Language.UNKNOWN.value

    def explain_code(self, code: str, detail_level: str = "medium") -> str:
        """Explain what code does.

        Args:
            code: Source code to explain
            detail_level: "brief", "medium", or "detailed"

        Returns:
            Explanation string
        """
        language = self.detect_language(code)

        # Build explanation prompt
        if detail_level == "brief":
            prompt = f"Briefly explain this {language} code in 1-2 sentences:\n\n```{language}\n{code}\n```"
        elif detail_level == "detailed":
            prompt = f"""Provide a detailed explanation of this {language} code:

```{language}
{code}
```

Include:
1. Overall purpose
2. Line-by-line breakdown
3. Key functions/methods used
4. Input/output behavior
5. Potential edge cases"""
        else:  # medium
            prompt = f"""Explain this {language} code:

```{language}
{code}
```

Describe what it does, its main components, and how they work together."""

        if HAS_OLLAMA and chat:
            try:
                response = chat(prompt, model=self.model)
                return response
            except Exception as e:
                return f"AI explanation unavailable: {e}\n\nLanguage detected: {language}"
        else:
            # Fallback: basic static analysis
            return self._static_explain(code, language)

    def _static_explain(self, code: str, language: str) -> str:
        """Provide basic static analysis without AI."""
        lines = code.strip().split('\n')
        line_count = len(lines)

        explanation = [f"Language: {language}", f"Lines: {line_count}"]

        if language == Language.PYTHON.value:
            # Count Python constructs
            functions = len(re.findall(r'\bdef \w+', code))
            classes = len(re.findall(r'\bclass \w+', code))
            imports = len(re.findall(r'^(?:import|from)\s+', code, re.MULTILINE))

            if functions:
                explanation.append(f"Functions: {functions}")
            if classes:
                explanation.append(f"Classes: {classes}")
            if imports:
                explanation.append(f"Imports: {imports}")

        elif language == Language.JAVASCRIPT.value:
            functions = len(re.findall(r'\bfunction\s+\w+|\b\w+\s*=\s*(?:async\s*)?\(', code))
            if functions:
                explanation.append(f"Functions: {functions}")

        return '\n'.join(explanation)

    def write_code(
        self,
        description: str,
        language: str = "python",
        include_comments: bool = True
    ) -> str:
        """Generate code from description.

        Args:
            description: What the code should do
            language: Target programming language
            include_comments: Whether to include explanatory comments

        Returns:
            Generated code string
        """
        comment_instruction = "Include helpful comments." if include_comments else "No comments needed."

        prompt = f"""Write {language} code that does the following:

{description}

Requirements:
- Clean, readable code
- Follow {language} best practices
- {comment_instruction}
- Only output the code, no explanations

```{language}"""

        if HAS_OLLAMA and chat:
            try:
                response = chat(prompt, model=self.model)
                # Extract code from response
                code = self._extract_code(response, language)
                return code
            except Exception as e:
                return f"# Code generation failed: {e}"
        else:
            return f"# AI code generation unavailable\n# Description: {description}"

    def _extract_code(self, response: str, language: str) -> str:
        """Extract code block from AI response."""
        # Try to find code block
        patterns = [
            rf'```{language}\n(.*?)```',
            r'```\n(.*?)```',
            rf'```{language}(.*?)```',
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # No code block found, return as-is (might be plain code)
        return response.strip()

    def fix_code(self, code: str, error: Optional[str] = None) -> str:
        """Fix errors in code.

        Args:
            code: Broken code
            error: Optional error message

        Returns:
            Fixed code string
        """
        language = self.detect_language(code)

        if error:
            prompt = f"""Fix this {language} code that has the following error:

Error: {error}

Code:
```{language}
{code}
```

Provide only the corrected code:"""
        else:
            prompt = f"""Review and fix any issues in this {language} code:

```{language}
{code}
```

Fix any bugs, syntax errors, or logic issues. Provide only the corrected code:"""

        if HAS_OLLAMA and chat:
            try:
                response = chat(prompt, model=self.model)
                return self._extract_code(response, language)
            except Exception as e:
                return f"# Fix failed: {e}\n{code}"
        else:
            return f"# AI code fixing unavailable\n{code}"

    def run_code(
        self,
        code: str,
        language: Optional[str] = None,
        timeout: int = 30,
        safe_mode: bool = True
    ) -> CodeResult:
        """Execute code and return results.

        Args:
            code: Code to execute
            language: Language (auto-detected if None)
            timeout: Execution timeout in seconds
            safe_mode: If True, restricts dangerous operations

        Returns:
            CodeResult with output and status
        """
        if language is None:
            language = self.detect_language(code)

        # Safety check
        if safe_mode and self._is_dangerous(code, language):
            return CodeResult(
                success=False,
                output="",
                error="Code contains potentially dangerous operations. Use safe_mode=False to override.",
                return_code=-1,
                language=language
            )

        if language == Language.PYTHON.value:
            return self._run_python(code, timeout)
        elif language == Language.JAVASCRIPT.value:
            return self._run_javascript(code, timeout)
        elif language == Language.BASH.value:
            return self._run_bash(code, timeout)
        elif language == Language.POWERSHELL.value:
            return self._run_powershell(code, timeout)
        else:
            return CodeResult(
                success=False,
                output="",
                error=f"Cannot execute {language} code directly",
                return_code=-1,
                language=language
            )

    def _is_dangerous(self, code: str, language: str) -> bool:
        """Check if code contains dangerous operations."""
        dangerous_patterns = [
            r'\brm\s+-rf\b',
            r'\bformat\s+[a-z]:\b',
            r'\bdel\s+/[sf]\b',
            r'os\.remove|os\.unlink|shutil\.rmtree',
            r'subprocess\.call.*shell\s*=\s*True',
            r'\beval\s*\(',
            r'\bexec\s*\(',
            r'__import__',
            r'open\s*\([^)]*["\']w["\']',
            r'DROP\s+TABLE|DELETE\s+FROM|TRUNCATE',
        ]

        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True

        return False

    def _run_python(self, code: str, timeout: int) -> CodeResult:
        """Execute Python code."""
        # Write to temp file
        temp_file = self._temp_dir / "temp_script.py"
        temp_file.write_text(code, encoding='utf-8')

        try:
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._temp_dir)
            )
            return CodeResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode,
                language=Language.PYTHON.value
            )
        except subprocess.TimeoutExpired:
            return CodeResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout} seconds",
                return_code=-1,
                language=Language.PYTHON.value
            )
        except Exception as e:
            return CodeResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                language=Language.PYTHON.value
            )
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def _run_javascript(self, code: str, timeout: int) -> CodeResult:
        """Execute JavaScript code using Node.js."""
        temp_file = self._temp_dir / "temp_script.js"
        temp_file.write_text(code, encoding='utf-8')

        try:
            result = subprocess.run(
                ["node", str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._temp_dir)
            )
            return CodeResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode,
                language=Language.JAVASCRIPT.value
            )
        except FileNotFoundError:
            return CodeResult(
                success=False,
                output="",
                error="Node.js not found. Install Node.js to run JavaScript.",
                return_code=-1,
                language=Language.JAVASCRIPT.value
            )
        except subprocess.TimeoutExpired:
            return CodeResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout} seconds",
                return_code=-1,
                language=Language.JAVASCRIPT.value
            )
        except Exception as e:
            return CodeResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                language=Language.JAVASCRIPT.value
            )
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def _run_bash(self, code: str, timeout: int) -> CodeResult:
        """Execute Bash code."""
        try:
            result = subprocess.run(
                ["bash", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._temp_dir)
            )
            return CodeResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode,
                language=Language.BASH.value
            )
        except FileNotFoundError:
            # Try sh on Windows
            try:
                result = subprocess.run(
                    ["sh", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self._temp_dir)
                )
                return CodeResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode,
                    language=Language.BASH.value
                )
            except FileNotFoundError:
                return CodeResult(
                    success=False,
                    output="",
                    error="Bash/sh not found. Install Git Bash or WSL on Windows.",
                    return_code=-1,
                    language=Language.BASH.value
                )
        except subprocess.TimeoutExpired:
            return CodeResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout} seconds",
                return_code=-1,
                language=Language.BASH.value
            )
        except Exception as e:
            return CodeResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                language=Language.BASH.value
            )

    def _run_powershell(self, code: str, timeout: int) -> CodeResult:
        """Execute PowerShell code."""
        try:
            result = subprocess.run(
                ["powershell", "-Command", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._temp_dir)
            )
            return CodeResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode,
                language=Language.POWERSHELL.value
            )
        except FileNotFoundError:
            return CodeResult(
                success=False,
                output="",
                error="PowerShell not found.",
                return_code=-1,
                language=Language.POWERSHELL.value
            )
        except subprocess.TimeoutExpired:
            return CodeResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout} seconds",
                return_code=-1,
                language=Language.POWERSHELL.value
            )
        except Exception as e:
            return CodeResult(
                success=False,
                output="",
                error=str(e),
                return_code=-1,
                language=Language.POWERSHELL.value
            )

    def analyze_code(self, code: str) -> CodeAnalysis:
        """Analyze code for issues and suggestions.

        Args:
            code: Code to analyze

        Returns:
            CodeAnalysis with findings
        """
        language = self.detect_language(code)

        prompt = f"""Analyze this {language} code:

```{language}
{code}
```

Provide:
1. Brief summary (one sentence)
2. Detailed explanation
3. List of issues/bugs found
4. List of improvement suggestions

Format as:
SUMMARY: ...
EXPLANATION: ...
ISSUES:
- issue 1
- issue 2
SUGGESTIONS:
- suggestion 1
- suggestion 2"""

        if HAS_OLLAMA and chat:
            try:
                response = chat(prompt, model=self.model)
                return self._parse_analysis(response, language)
            except Exception as e:
                pass

        # Fallback to basic static analysis
        return CodeAnalysis(
            language=language,
            summary=f"{language} code with {len(code.splitlines())} lines",
            explanation=self._static_explain(code, language),
            issues=[],
            suggestions=[]
        )

    def _parse_analysis(self, response: str, language: str) -> CodeAnalysis:
        """Parse AI analysis response."""
        summary = ""
        explanation = ""
        issues = []
        suggestions = []

        # Extract sections
        if "SUMMARY:" in response:
            match = re.search(r'SUMMARY:\s*(.+?)(?=EXPLANATION:|ISSUES:|$)', response, re.DOTALL)
            if match:
                summary = match.group(1).strip()

        if "EXPLANATION:" in response:
            match = re.search(r'EXPLANATION:\s*(.+?)(?=ISSUES:|SUGGESTIONS:|$)', response, re.DOTALL)
            if match:
                explanation = match.group(1).strip()

        if "ISSUES:" in response:
            match = re.search(r'ISSUES:\s*(.+?)(?=SUGGESTIONS:|$)', response, re.DOTALL)
            if match:
                issues_text = match.group(1)
                issues = [line.strip().lstrip('- ') for line in issues_text.split('\n')
                         if line.strip() and line.strip() != '-']

        if "SUGGESTIONS:" in response:
            match = re.search(r'SUGGESTIONS:\s*(.+?)$', response, re.DOTALL)
            if match:
                sugg_text = match.group(1)
                suggestions = [line.strip().lstrip('- ') for line in sugg_text.split('\n')
                              if line.strip() and line.strip() != '-']

        return CodeAnalysis(
            language=language,
            summary=summary or "Code analysis complete",
            explanation=explanation or response,
            issues=issues,
            suggestions=suggestions
        )
