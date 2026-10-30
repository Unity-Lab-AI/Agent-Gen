"""
C.O.R.A System Tools Module

System control and monitoring capabilities.
Per ARCHITECTURE.md: Launch apps, get specs, monitor performance.
"""

import os
import subprocess
import platform
import shutil


def get_system_info():
    """Get basic system information.

    Returns:
        dict: System specs including OS, CPU, memory, etc.
    """
    info = {
        'os': platform.system(),
        'os_version': platform.version(),
        'os_release': platform.release(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
    }

    # Get disk space
    try:
        total, used, free = shutil.disk_usage('/')
        info['disk_total_gb'] = round(total / (1024**3), 2)
        info['disk_free_gb'] = round(free / (1024**3), 2)
    except Exception:
        pass

    return info


def launch_app(app_name):
    """Launch an application by name.

    Args:
        app_name: Name or path of application to launch

    Returns:
        bool: True if launched successfully
    """
    try:
        if platform.system() == 'Windows':
            os.startfile(app_name)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', app_name])
        else:  # Linux
            subprocess.run(['xdg-open', app_name])
        return True
    except Exception as e:
        print(f"Failed to launch {app_name}: {e}")
        return False


def open_file(file_path):
    """Open a file with the default application.

    Args:
        file_path: Path to the file

    Returns:
        bool: True if opened successfully
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False

    return launch_app(file_path)


def open_folder(folder_path):
    """Open a folder in the file explorer.

    Args:
        folder_path: Path to the folder

    Returns:
        bool: True if opened successfully
    """
    if not os.path.isdir(folder_path):
        print(f"Folder not found: {folder_path}")
        return False

    try:
        if platform.system() == 'Windows':
            os.startfile(folder_path)
        elif platform.system() == 'Darwin':
            subprocess.run(['open', folder_path])
        else:
            subprocess.run(['xdg-open', folder_path])
        return True
    except Exception as e:
        print(f"Failed to open folder: {e}")
        return False


def search_files(query, path=None, extensions=None):
    """Search for files by name.

    Args:
        query: Search term (partial filename)
        path: Directory to search (defaults to user home)
        extensions: List of file extensions to filter (e.g., ['.txt', '.py'])

    Returns:
        list: Matching file paths
    """
    if path is None:
        path = os.path.expanduser('~')

    matches = []
    query_lower = query.lower()

    try:
        for root, dirs, files in os.walk(path):
            # Skip hidden and system directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for file in files:
                if query_lower in file.lower():
                    if extensions is None or any(file.endswith(ext) for ext in extensions):
                        matches.append(os.path.join(root, file))

                if len(matches) >= 50:  # Limit results
                    return matches
    except PermissionError:
        pass

    return matches


def get_running_processes():
    """Get list of running processes (Windows).

    Returns:
        list: Process names
    """
    if platform.system() != 'Windows':
        return []

    try:
        result = subprocess.run(
            ['tasklist', '/FO', 'CSV', '/NH'],
            capture_output=True,
            text=True
        )
        processes = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split(',')
                if parts:
                    name = parts[0].strip('"')
                    processes.append(name)
        return processes
    except Exception:
        return []


def kill_process(process_name):
    """Kill a process by name (Windows).

    Args:
        process_name: Name of process to kill

    Returns:
        bool: True if killed successfully
    """
    if platform.system() != 'Windows':
        return False

    try:
        result = subprocess.run(
            ['taskkill', '/IM', process_name, '/F'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_gpu_info():
    """Get GPU information (NVIDIA only).

    Returns:
        dict: GPU name, memory, utilization (if nvidia-smi available)
    """
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) >= 4:
                return {
                    'name': parts[0].strip(),
                    'memory_total_mb': int(parts[1].strip()),
                    'memory_used_mb': int(parts[2].strip()),
                    'utilization_percent': int(parts[3].strip())
                }
    except Exception:
        pass

    return None


def get_memory_usage():
    """Get system memory usage.

    Returns:
        dict: Memory total, used, available (if available)
    """
    try:
        if platform.system() == 'Windows':
            # Use wmic on Windows
            result = subprocess.run(
                ['wmic', 'OS', 'get', 'TotalVisibleMemorySize,FreePhysicalMemory', '/value'],
                capture_output=True,
                text=True
            )
            lines = result.stdout.strip().split('\n')
            total = free = 0
            for line in lines:
                if 'TotalVisibleMemorySize' in line:
                    total = int(line.split('=')[1].strip()) // 1024  # Convert KB to MB
                elif 'FreePhysicalMemory' in line:
                    free = int(line.split('=')[1].strip()) // 1024
            return {
                'total_mb': total,
                'free_mb': free,
                'used_mb': total - free
            }
    except Exception:
        pass

    return None


def set_volume(level):
    """Set system volume (Windows only).

    Args:
        level: Volume level 0-100

    Returns:
        bool: True if set successfully
    """
    if platform.system() != 'Windows':
        return False

    try:
        # Clamp to 0-100
        level = max(0, min(100, int(level)))
        # Use nircmd if available, otherwise powershell
        try:
            subprocess.run(['nircmd', 'setsysvolume', str(level * 655)], timeout=5)
        except FileNotFoundError:
            # Fallback to PowerShell
            ps_cmd = f'(New-Object -ComObject WScript.Shell).SendKeys([char]173)'
            subprocess.run(['powershell', '-Command', ps_cmd], timeout=5)
        return True
    except Exception as e:
        print(f"Failed to set volume: {e}")
        return False


def _escape_powershell_string(s: str) -> str:
    """Escape a string for safe use in PowerShell commands.

    Args:
        s: String to escape

    Returns:
        Escaped string safe for PowerShell
    """
    if not s:
        return ''
    # Remove any null bytes or control characters first
    s = ''.join(c for c in s if ord(c) >= 32 or c in '\t\n\r')
    # Escape in correct order: backticks first, then other special chars
    s = s.replace('`', '``')      # Backticks (escape char)
    s = s.replace('"', '`"')      # Double quotes
    s = s.replace("'", "''")      # Single quotes (doubled in PS)
    s = s.replace('$', '`$')      # Variable expansion
    s = s.replace('#', '`#')      # Comments
    s = s.replace('&', '`&')      # Command chaining
    s = s.replace('|', '`|')      # Pipe
    s = s.replace(';', '`;')      # Statement separator
    s = s.replace('(', '`(')      # Subexpression
    s = s.replace(')', '`)')
    s = s.replace('{', '`{')      # Script block
    s = s.replace('}', '`}')
    s = s.replace('<', '`<')      # Redirection
    s = s.replace('>', '`>')
    # Limit length to prevent DoS
    return s[:1000]


def notify(title, message, duration=5):
    """Show Windows toast notification.

    Args:
        title: Notification title
        message: Notification message
        duration: Duration in seconds

    Returns:
        bool: True if shown successfully
    """
    if platform.system() != 'Windows':
        return False

    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration, threaded=True)
        return True
    except ImportError:
        # Fallback to PowerShell BurntToast - escape inputs to prevent injection
        try:
            safe_title = _escape_powershell_string(str(title))
            safe_message = _escape_powershell_string(str(message))
            ps_cmd = f'New-BurntToastNotification -Text "{safe_title}", "{safe_message}"'
            subprocess.run(['powershell', '-Command', ps_cmd], timeout=10)
            return True
        except Exception:
            pass
    return False


def clipboard_paste():
    """Get clipboard contents.

    Returns:
        str: Clipboard text or None
    """
    try:
        if platform.system() == 'Windows':
            result = subprocess.run(
                ['powershell', '-Command', 'Get-Clipboard'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        elif platform.system() == 'Darwin':
            result = subprocess.run(['pbpaste'], capture_output=True, text=True)
            return result.stdout
        else:
            result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'],
                                  capture_output=True, text=True)
            return result.stdout
    except Exception as e:
        print(f"Failed to get clipboard: {e}")
        return None


def clipboard_copy(text):
    """Copy text to clipboard.

    Args:
        text: Text to copy

    Returns:
        bool: True if copied successfully
    """
    try:
        text_str = str(text) if text else ''
        if platform.system() == 'Windows':
            # Use stdin piping - no string interpolation, no injection risk
            subprocess.run(
                ['powershell', '-Command', '$input | Set-Clipboard'],
                input=text_str.encode('utf-8'),
                timeout=5
            )
        elif platform.system() == 'Darwin':
            subprocess.run(['pbcopy'], input=text_str.encode(), timeout=5)
        else:
            subprocess.run(['xclip', '-selection', 'clipboard'],
                         input=text_str.encode(), timeout=5)
        return True
    except Exception as e:
        print(f"Failed to copy to clipboard: {e}")
        return False


def maximize_window(window_name):
    """Maximize a window by name (Windows only).

    Args:
        window_name: Partial window title

    Returns:
        bool: True if maximized
    """
    if platform.system() != 'Windows':
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_MAXIMIZE = 3

        def enum_callback(hwnd, found):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                title = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title, length + 1)
                if window_name.lower() in title.value.lower():
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)
                    found.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.py_object)
        found = []
        user32.EnumWindows(WNDENUMPROC(enum_callback), found)
        return len(found) > 0
    except Exception as e:
        print(f"Failed to maximize window: {e}")
        return False


def focus_window(window_name):
    """Bring a window to focus by name (Windows only).

    Args:
        window_name: Partial window title

    Returns:
        bool: True if focused
    """
    if platform.system() != 'Windows':
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        def enum_callback(hwnd, found):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                title = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title, length + 1)
                if window_name.lower() in title.value.lower():
                    user32.SetForegroundWindow(hwnd)
                    found.append(hwnd)
                    return False  # Stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.py_object)
        found = []
        user32.EnumWindows(WNDENUMPROC(enum_callback), found)
        return len(found) > 0
    except Exception as e:
        print(f"Failed to focus window: {e}")
        return False


def fetch_url(url, timeout=30):
    """Fetch URL content.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        str: Response text or None
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'CORA/2.0'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch URL: {e}")
        return None


def take_screenshot(save_path=None):
    """Take a screenshot.

    Args:
        save_path: Optional path to save screenshot

    Returns:
        str: Path to screenshot or None
    """
    try:
        from PIL import ImageGrab
        import tempfile

        img = ImageGrab.grab()

        if save_path is None:
            save_path = os.path.join(tempfile.gettempdir(), 'cora_screenshot.png')

        img.save(save_path)
        return save_path
    except ImportError:
        print("PIL not installed. Run: pip install Pillow")
        return None
    except Exception as e:
        print(f"Screenshot failed: {e}")
        return None


def calculate(expression: str) -> dict:
    """Safely evaluate a math expression using AST parsing.

    Args:
        expression: Math expression like "2 + 2" or "sqrt(16)"

    Returns:
        dict: {'success': bool, 'result': number, 'expression': str}
    """
    import ast
    import math
    import operator
    import re

    if not expression or not expression.strip():
        return {'success': False, 'error': 'Empty expression'}

    expr = expression.strip()

    # Replace common symbols before parsing
    expr = expr.replace('^', '**')  # Power operator
    expr = expr.replace('×', '*')
    expr = expr.replace('÷', '/')

    # Allowed math functions and constants
    SAFE_FUNCTIONS = {
        'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'log': math.log, 'log10': math.log10, 'exp': math.exp, 'pow': pow,
        'abs': abs, 'round': round, 'floor': math.floor, 'ceil': math.ceil
    }
    SAFE_CONSTANTS = {'pi': math.pi, 'e': math.e}

    # Allowed binary operators
    SAFE_OPERATORS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv
    }
    SAFE_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    def _safe_eval(node):
        """Recursively evaluate AST node with safety checks."""
        if isinstance(node, ast.Constant):  # Numbers
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.Num):  # Python 3.7 compat
            return node.n
        elif isinstance(node, ast.Name):  # Constants like pi, e
            if node.id.lower() in SAFE_CONSTANTS:
                return SAFE_CONSTANTS[node.id.lower()]
            raise ValueError(f"Unknown variable: {node.id}")
        elif isinstance(node, ast.BinOp):  # Binary operations
            if type(node.op) not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            left = _safe_eval(node.left)
            right = _safe_eval(node.right)
            return SAFE_OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):  # Unary operations (-x, +x)
            if type(node.op) not in SAFE_UNARY:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return SAFE_UNARY[type(node.op)](_safe_eval(node.operand))
        elif isinstance(node, ast.Call):  # Function calls
            if not isinstance(node.func, ast.Name):
                raise ValueError("Complex function calls not allowed")
            func_name = node.func.id.lower()
            if func_name not in SAFE_FUNCTIONS:
                raise ValueError(f"Unknown function: {node.func.id}")
            args = [_safe_eval(arg) for arg in node.args]
            return SAFE_FUNCTIONS[func_name](*args)
        elif isinstance(node, ast.Expression):
            return _safe_eval(node.body)
        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")

    try:
        # Parse expression into AST
        tree = ast.parse(expr, mode='eval')
        result = _safe_eval(tree)
        return {
            'success': True,
            'expression': expression.strip(),
            'result': result
        }
    except ZeroDivisionError:
        return {'success': False, 'error': 'Division by zero'}
    except SyntaxError as e:
        return {'success': False, 'error': f'Invalid syntax: {e}'}
    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': f'Calculation error: {e}'}


def run_shell(command: str, timeout: int = 30) -> dict:
    """Run a shell command safely.

    Args:
        command: Shell command to run
        timeout: Maximum execution time in seconds

    Returns:
        dict: {'success': bool, 'output': str, 'error': str}
    """
    import shlex

    if not command or not command.strip():
        return {'success': False, 'error': 'Empty command'}

    # Safety: Block dangerous commands
    dangerous = [
        'rm -rf', 'rm -r', 'del /f', 'del /s', 'format', 'shutdown', 'rmdir /s',
        'drop table', 'delete from', 'truncate', 'mkfs', ':(){', 'fork bomb',
        '> /dev/sda', 'dd if=', 'chmod 777', 'chmod -r', 'curl | sh', 'wget | sh',
        'eval(', 'exec(', 'sudo rm', 'rd /s', 'taskkill /f /im', 'net user', 'reg delete',
        'powershell -enc', 'iex(', 'invoke-expression', 'set-executionpolicy'
    ]

    cmd_lower = command.lower().replace('  ', ' ')
    for d in dangerous:
        if d in cmd_lower:
            return {'success': False, 'error': f'Blocked: "{d}" is dangerous'}

    try:
        # Parse command safely without shell=True
        # On Windows, use cmd /c for shell features; on Unix use sh -c
        if platform.system() == 'Windows':
            # Use cmd.exe to handle Windows shell features safely
            cmd_args = ['cmd', '/c', command]
        else:
            # Use sh -c for Unix shell features
            cmd_args = ['sh', '-c', command]

        result = subprocess.run(
            cmd_args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='ignore'
        )

        output = result.stdout + result.stderr
        if len(output) > 5000:
            output = output[:5000] + '\n... [truncated]'

        return {
            'success': result.returncode == 0,
            'output': output or '(no output)',
            'return_code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Command timed out after {timeout}s'}
    except Exception as e:
        return {'success': False, 'error': f'Error: {e}'}
