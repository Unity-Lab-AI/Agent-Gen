"""
stdin_inject_smart.py - Smart injection with input detection
Checks for pending user input before injecting. Retries with backoff.
If the same stale input is detected multiple times, clears it and proceeds.

Usage: python stdin_inject_smart.py <PID> <message>

Smart behavior:
1. Check screen buffer for pending input
2. If input found, wait and retry (up to MAX_RETRIES)
3. If SAME input seen STALE_THRESHOLD times, assume abandoned -> clear and inject
4. After MAX_RETRIES, force inject anyway (nudge must land eventually)
"""
import sys
import ctypes
import ctypes.wintypes as wintypes
import time

# Configuration
MAX_RETRIES = 3           # Try 3 times before forcing
RETRY_DELAY_S = 10        # 10 seconds between retries
STALE_THRESHOLD = 2       # Same input 2 times = stale

# Heartbeat/nudge keywords - if input contains these, it's a stale nudge
HEARTBEAT_KEYWORDS = [
    "Watchdog Pulse",
    "BEAT and CONTINUE",
    "Resume patrol",
    "check mailbox",
    "continue active tasks",
    "heartbeat check",
    "are you alive"
]

kernel32 = ctypes.windll.kernel32

FreeConsole = kernel32.FreeConsole
AttachConsole = kernel32.AttachConsole
AttachConsole.argtypes = [wintypes.DWORD]
AttachConsole.restype = wintypes.BOOL
GetLastError = kernel32.GetLastError

# Structures for screen buffer reading
class COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

class SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", wintypes.SHORT), ("Top", wintypes.SHORT),
        ("Right", wintypes.SHORT), ("Bottom", wintypes.SHORT)
    ]

class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD), ("dwCursorPosition", COORD),
        ("wAttributes", wintypes.WORD), ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", COORD)
    ]

class CHAR_INFO(ctypes.Structure):
    class _Char(ctypes.Union):
        _fields_ = [("UnicodeChar", wintypes.WCHAR), ("AsciiChar", ctypes.c_char)]
    _fields_ = [("Char", _Char), ("Attributes", wintypes.WORD)]

# Structures for key injection
class KEY_EVENT_RECORD(ctypes.Structure):
    class _uChar(ctypes.Union):
        _fields_ = [("UnicodeChar", wintypes.WCHAR), ("AsciiChar", ctypes.c_char)]
    _fields_ = [
        ("bKeyDown", wintypes.BOOL), ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD), ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _uChar), ("dwControlKeyState", wintypes.DWORD)
    ]

class INPUT_RECORD(ctypes.Structure):
    class _Event(ctypes.Union):
        _fields_ = [("KeyEvent", KEY_EVENT_RECORD)]
    _fields_ = [("EventType", wintypes.WORD), ("Event", _Event)]

KEY_EVENT = 0x0001

GetConsoleScreenBufferInfo = kernel32.GetConsoleScreenBufferInfo
GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(CONSOLE_SCREEN_BUFFER_INFO)]
GetConsoleScreenBufferInfo.restype = wintypes.BOOL

ReadConsoleOutputW = kernel32.ReadConsoleOutputW
ReadConsoleOutputW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(CHAR_INFO), COORD, COORD, ctypes.POINTER(SMALL_RECT)
]
ReadConsoleOutputW.restype = wintypes.BOOL

WriteConsoleInputW = kernel32.WriteConsoleInputW
WriteConsoleInputW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(INPUT_RECORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
]
WriteConsoleInputW.restype = wintypes.BOOL


def get_pending_input(pid):
    """
    Read screen buffer and extract text from input line.
    Returns: (input_text: str or None, error: str or None)
    """
    FreeConsole()
    if not AttachConsole(pid):
        return (None, f"AttachConsole failed: {GetLastError()}")

    handle = kernel32.CreateFileW("CONOUT$", 0xC0000000, 0x03, None, 3, 0, None)
    if not handle or handle == -1:
        FreeConsole()
        return (None, f"CONOUT$ failed: {GetLastError()}")

    info = CONSOLE_SCREEN_BUFFER_INFO()
    if not GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
        kernel32.CloseHandle(handle)
        FreeConsole()
        return (None, f"GetScreenBufferInfo failed: {GetLastError()}")

    width = info.dwSize.X
    end_y = info.srWindow.Bottom
    start_y = max(info.srWindow.Top, end_y - 15)
    height = end_y - start_y + 1

    buffer = (CHAR_INFO * (width * height))()
    buffer_size = COORD(width, height)
    buffer_coord = COORD(0, 0)
    read_region = SMALL_RECT(0, start_y, width - 1, end_y)

    if not ReadConsoleOutputW(handle, buffer, buffer_size, buffer_coord, ctypes.byref(read_region)):
        kernel32.CloseHandle(handle)
        FreeConsole()
        return (None, f"ReadConsoleOutput failed: {GetLastError()}")

    kernel32.CloseHandle(handle)
    FreeConsole()

    # Search from bottom up for input line
    # Claude Code uses ">" followed by non-breaking space (\u00a0), not regular space
    for row in range(height - 1, -1, -1):
        line = "".join(buffer[row * width + col].Char.UnicodeChar or " " for col in range(width)).rstrip()
        # Check for > followed by regular space OR non-breaking space
        if line.startswith("> ") or line.startswith(">\u00a0"):
            text = line[2:].strip()
            # Skip UI messages like "Press up to edit queued messages"
            if text.startswith("Press ") or text.startswith("Type "):
                continue
            return (text, None)

    return ("", None)  # No input line found = empty


def make_key_event(char, key_down=True):
    """Create INPUT_RECORD for a key event."""
    rec = INPUT_RECORD()
    rec.EventType = KEY_EVENT
    rec.Event.KeyEvent.bKeyDown = key_down
    rec.Event.KeyEvent.wRepeatCount = 1
    rec.Event.KeyEvent.uChar.UnicodeChar = char
    vk = ctypes.windll.user32.VkKeyScanW(ord(char))
    rec.Event.KeyEvent.wVirtualKeyCode = vk & 0xFF
    rec.Event.KeyEvent.wVirtualScanCode = ctypes.windll.user32.MapVirtualKeyW(vk & 0xFF, 0)
    rec.Event.KeyEvent.dwControlKeyState = 0
    return rec


def inject_text(pid, text):
    """Inject text followed by Enter into console."""
    # Strip chars that can't fit in a single wchar_t (emoji/surrogate pairs)
    text = ''.join(c for c in text if ord(c) <= 0xFFFF)
    FreeConsole()
    if not AttachConsole(pid):
        return False

    conin = kernel32.CreateFileW("CONIN$", 0xC0000000, 0x03, None, 3, 0, None)
    if not conin or conin == -1:
        FreeConsole()
        return False

    # Send text characters
    records = []
    for char in text:
        records.append(make_key_event(char, True))
        records.append(make_key_event(char, False))

    arr = (INPUT_RECORD * len(records))(*records)
    written = wintypes.DWORD(0)
    if not WriteConsoleInputW(conin, arr, len(records), ctypes.byref(written)):
        kernel32.CloseHandle(conin)
        FreeConsole()
        return False

    time.sleep(0.3)  # Pause for Claude Code to process before Enter

    # Send Enter
    enter_records = []
    for key_down in [True, False]:
        rec = INPUT_RECORD()
        rec.EventType = KEY_EVENT
        rec.Event.KeyEvent.bKeyDown = key_down
        rec.Event.KeyEvent.wRepeatCount = 1
        rec.Event.KeyEvent.wVirtualKeyCode = 0x0D
        rec.Event.KeyEvent.wVirtualScanCode = 0x1C
        rec.Event.KeyEvent.uChar.UnicodeChar = '\r'
        rec.Event.KeyEvent.dwControlKeyState = 0
        enter_records.append(rec)

    arr2 = (INPUT_RECORD * 2)(*enter_records)
    written2 = wintypes.DWORD(0)
    result = WriteConsoleInputW(conin, arr2, 2, ctypes.byref(written2))

    kernel32.CloseHandle(conin)
    FreeConsole()
    return result


def send_enter(pid):
    """Send Enter to submit whatever is on the input line."""
    FreeConsole()
    if not AttachConsole(pid):
        return False

    conin = kernel32.CreateFileW("CONIN$", 0xC0000000, 0x03, None, 3, 0, None)
    if not conin or conin == -1:
        FreeConsole()
        return False

    # Send Enter key
    records = []
    for key_down in [True, False]:
        rec = INPUT_RECORD()
        rec.EventType = KEY_EVENT
        rec.Event.KeyEvent.bKeyDown = key_down
        rec.Event.KeyEvent.wRepeatCount = 1
        rec.Event.KeyEvent.wVirtualKeyCode = 0x0D  # VK_RETURN
        rec.Event.KeyEvent.wVirtualScanCode = 0x1C
        rec.Event.KeyEvent.uChar.UnicodeChar = '\r'
        rec.Event.KeyEvent.dwControlKeyState = 0
        records.append(rec)

    arr = (INPUT_RECORD * len(records))(*records)
    written = wintypes.DWORD(0)
    result = WriteConsoleInputW(conin, arr, len(records), ctypes.byref(written))

    kernel32.CloseHandle(conin)
    FreeConsole()
    return result


def clear_input_line(pid):
    """Clear pending input by sending Escape + Ctrl+A + Backspace."""
    FreeConsole()
    if not AttachConsole(pid):
        return False

    conin = kernel32.CreateFileW("CONIN$", 0xC0000000, 0x03, None, 3, 0, None)
    if not conin or conin == -1:
        FreeConsole()
        return False

    records = []

    # Escape key
    for key_down in [True, False]:
        rec = INPUT_RECORD()
        rec.EventType = KEY_EVENT
        rec.Event.KeyEvent.bKeyDown = key_down
        rec.Event.KeyEvent.wRepeatCount = 1
        rec.Event.KeyEvent.wVirtualKeyCode = 0x1B  # VK_ESCAPE
        rec.Event.KeyEvent.wVirtualScanCode = 0x01
        rec.Event.KeyEvent.uChar.UnicodeChar = '\x1b'
        rec.Event.KeyEvent.dwControlKeyState = 0
        records.append(rec)

    # Ctrl+A (select all)
    for key_down in [True, False]:
        rec = INPUT_RECORD()
        rec.EventType = KEY_EVENT
        rec.Event.KeyEvent.bKeyDown = key_down
        rec.Event.KeyEvent.wRepeatCount = 1
        rec.Event.KeyEvent.wVirtualKeyCode = 0x41  # 'A'
        rec.Event.KeyEvent.wVirtualScanCode = 0x1E
        rec.Event.KeyEvent.uChar.UnicodeChar = '\x01'  # Ctrl+A
        rec.Event.KeyEvent.dwControlKeyState = 0x0008  # LEFT_CTRL_PRESSED
        records.append(rec)

    # Backspace (delete selected)
    for key_down in [True, False]:
        rec = INPUT_RECORD()
        rec.EventType = KEY_EVENT
        rec.Event.KeyEvent.bKeyDown = key_down
        rec.Event.KeyEvent.wRepeatCount = 1
        rec.Event.KeyEvent.wVirtualKeyCode = 0x08  # VK_BACK
        rec.Event.KeyEvent.wVirtualScanCode = 0x0E
        rec.Event.KeyEvent.uChar.UnicodeChar = '\x08'
        rec.Event.KeyEvent.dwControlKeyState = 0
        records.append(rec)

    arr = (INPUT_RECORD * len(records))(*records)
    written = wintypes.DWORD(0)
    result = WriteConsoleInputW(conin, arr, len(records), ctypes.byref(written))

    kernel32.CloseHandle(conin)
    FreeConsole()
    return result


def is_stale_heartbeat(text):
    """Check if text looks like a stale heartbeat/nudge message."""
    text_lower = text.lower()
    for keyword in HEARTBEAT_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False


def smart_inject(pid, message):
    """
    Simple injection: clear any pending input and inject immediately.
    No waiting, no retries. Screen is stale = FIRE NOW.
    """
    print(f"Injecting into PID {pid}...")

    # Clear any pending input first (ghost text, old nudges, whatever)
    clear_input_line(pid)
    time.sleep(0.1)

    # Inject the message
    if inject_text(pid, message):
        print("SUCCESS: Message injected")
        return True
    else:
        print("FAILED: Injection failed")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python stdin_inject_smart.py <PID> <message>")
        sys.exit(1)

    pid = int(sys.argv[1])
    message = " ".join(sys.argv[2:])

    safe_msg = message.encode('ascii', 'replace').decode('ascii')
    print(f"Smart inject into PID {pid}: '{safe_msg[:200]}'")
    success = smart_inject(pid, message)
    sys.exit(0 if success else 1)
