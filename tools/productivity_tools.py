import os
import sys
import subprocess
import threading
import datetime
import pyautogui
import pyperclip

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OS


def take_screenshot() -> str:
    desktop = os.path.expanduser("~/Desktop")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = os.path.join(desktop, filename)
    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        return f"Screenshot saved: {filename}"
    except Exception as e:
        return f"Failed to take screenshot: {e}"


def read_clipboard() -> str:
    try:
        content = pyperclip.paste()
        if not content:
            return "Clipboard is empty."
        return content[:300]
    except Exception as e:
        return f"Failed to read clipboard: {e}"


def control_volume(action: str) -> str:
    action = action.lower().strip()
    try:
        if OS == "Darwin":
            if action == "up":
                subprocess.run(
                    ["osascript", "-e", "set volume output volume (output volume of (get volume settings) + 10)"]
                )
            elif action == "down":
                subprocess.run(
                    ["osascript", "-e", "set volume output volume (output volume of (get volume settings) - 10)"]
                )
            elif action == "mute":
                subprocess.run(
                    ["osascript", "-e", "set volume with output muted"]
                )
            else:
                return f"Unknown volume action: '{action}'. Use 'up', 'down', or 'mute'."
        else:
            if action == "up":
                pyautogui.press("volumeup")
            elif action == "down":
                pyautogui.press("volumedown")
            elif action == "mute":
                pyautogui.press("volumemute")
            else:
                return f"Unknown volume action: '{action}'. Use 'up', 'down', or 'mute'."
        return f"Volume {action}."
    except Exception as e:
        return f"Failed to control volume: {e}"


def start_focus_timer(minutes: int) -> str:
    from speaker.tts import speak

    def _done():
        speak(f"Focus time is up! You've been focused for {minutes} minutes. Great work!")

    try:
        minutes = int(minutes)
        t = threading.Timer(minutes * 60, _done)
        t.daemon = True
        t.start()
        return f"Focus timer started for {minutes} minutes."
    except Exception as e:
        return f"Failed to start focus timer: {e}"


def remind_me(minutes: int, message: str) -> str:
    from speaker.tts import speak

    def _remind():
        speak(f"Reminder: {message}")

    try:
        minutes = int(minutes)
        t = threading.Timer(minutes * 60, _remind)
        t.daemon = True
        t.start()
        return f"Reminder set for {minutes} minutes: '{message}'"
    except Exception as e:
        return f"Failed to set reminder: {e}"
