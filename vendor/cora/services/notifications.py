#!/usr/bin/env python3
"""
C.O.R.A Notifications Service
System notifications and toast alerts for Windows

Per ARCHITECTURE.md:
- Show system notifications
- Toast notifications with icons
- Non-blocking alerts
"""

import os
import sys
import threading
from typing import Optional, Callable


def notify(title: str, message: str, icon: Optional[str] = None, duration: int = 5) -> bool:
    """Show a system notification.

    Args:
        title: Notification title
        message: Notification body text
        icon: Optional path to icon file
        duration: Duration in seconds (Windows default: 5)

    Returns:
        True if notification was shown
    """
    try:
        # Try Windows 10+ toast notifications first
        if sys.platform == 'win32':
            return _notify_windows(title, message, icon, duration)
        elif sys.platform == 'darwin':
            return _notify_macos(title, message)
        else:
            return _notify_linux(title, message, icon, duration)
    except Exception as e:
        print(f"[!] Notification failed: {e}")
        return False


def notify_toast(title: str, message: str, app_id: str = "CORA") -> bool:
    """Show a Windows toast notification.

    Args:
        title: Toast title
        message: Toast body
        app_id: Application identifier

    Returns:
        True if toast was shown
    """
    if sys.platform != 'win32':
        return notify(title, message)

    try:
        # Try win10toast first
        from win10toast import ToastNotifier

        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            duration=5,
            threaded=True
        )
        return True
    except ImportError:
        pass

    # Fallback to plyer
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name=app_id,
            timeout=5
        )
        return True
    except ImportError:
        pass

    # Fallback to powershell
    return _notify_powershell(title, message)


def notify_async(title: str, message: str, icon: Optional[str] = None,
                 callback: Optional[Callable] = None) -> None:
    """Show notification in background thread.

    Args:
        title: Notification title
        message: Notification body
        icon: Optional icon path
        callback: Optional callback when notification closes
    """
    def _notify_thread():
        result = notify(title, message, icon)
        if callback:
            callback(result)

    thread = threading.Thread(target=_notify_thread, daemon=True)
    thread.start()


def _notify_windows(title: str, message: str, icon: Optional[str], duration: int) -> bool:
    """Show Windows notification."""
    # Try multiple methods in order of preference

    # Method 1: win10toast
    try:
        from win10toast import ToastNotifier

        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            icon_path=icon,
            duration=duration,
            threaded=True
        )
        return True
    except ImportError:
        pass

    # Method 2: plyer
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_icon=icon,
            timeout=duration
        )
        return True
    except ImportError:
        pass

    # Method 3: PowerShell
    return _notify_powershell(title, message)


def _notify_powershell(title: str, message: str) -> bool:
    """Show notification via PowerShell (Windows fallback)."""
    try:
        import subprocess

        # Escape quotes in message
        title = title.replace('"', '`"')
        message = message.replace('"', '`"')

        ps_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("CORA").Show($toast)
        '''

        subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


def _notify_macos(title: str, message: str) -> bool:
    """Show macOS notification."""
    try:
        import subprocess

        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(['osascript', '-e', script], capture_output=True)
        return True
    except Exception:
        return False


def _notify_linux(title: str, message: str, icon: Optional[str], duration: int) -> bool:
    """Show Linux notification."""
    try:
        import subprocess

        cmd = ['notify-send', title, message]
        if icon:
            cmd.extend(['-i', icon])
        cmd.extend(['-t', str(duration * 1000)])

        subprocess.run(cmd, capture_output=True)
        return True
    except Exception:
        return False


def show_reminder(text: str, urgent: bool = False) -> bool:
    """Show a reminder notification.

    Args:
        text: Reminder text
        urgent: If True, show as urgent notification

    Returns:
        True if shown successfully
    """
    title = "CORA Reminder" if not urgent else "URGENT REMINDER"
    return notify(title, text)


def show_task_alert(task_id: str, task_text: str, due: Optional[str] = None) -> bool:
    """Show a task-related notification.

    Args:
        task_id: Task ID (e.g., T001)
        task_text: Task description
        due: Optional due date

    Returns:
        True if shown
    """
    if due:
        message = f"{task_id}: {task_text}\nDue: {due}"
    else:
        message = f"{task_id}: {task_text}"

    return notify("Task Alert", message)


if __name__ == "__main__":
    # Test notifications
    print("Testing notifications...")
    result = notify("CORA Test", "This is a test notification from CORA!")
    print(f"Result: {result}")
