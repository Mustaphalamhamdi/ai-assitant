"""
Human-like PC control tools — keyboard typing, key presses, and waiting.
These let Aria visibly control the computer the same way a human would:
open a terminal, type commands, read the screen, react, and repeat.

Requirements: macOS Accessibility permissions must be granted to the terminal
running Aria (System Preferences → Privacy & Security → Accessibility).
"""
import subprocess
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Key code table (macOS hardware key codes) ─────────────────────────────────
_KEY_CODES = {
    "return": 36, "enter": 36,
    "escape": 53, "esc": 53,
    "tab": 48,
    "space": 49,
    "delete": 51, "backspace": 51,
    "backtick": 50, "`": 50,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "f1": 122, "f2": 120, "f3": 99,  "f4": 118,
    "f5": 96,  "f6": 97,  "f7": 98,  "f8": 100,
    "f9": 101, "f10": 109,"f11": 103,"f12": 111,
}

_MODIFIER_MAP = {
    "cmd":     "command down",
    "command": "command down",
    "ctrl":    "control down",
    "control": "control down",
    "opt":     "option down",
    "alt":     "option down",
    "option":  "option down",
    "shift":   "shift down",
}


def type_text(text: str) -> str:
    """
    Type text at the current cursor position, exactly like a human typing.
    Uses clipboard paste for reliability — works for long prompts too.
    """
    try:
        # Put text in clipboard
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        time.sleep(0.15)
        # Paste with Cmd+V
        script = 'tell application "System Events" to keystroke "v" using {command down}'
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True)
        if result.returncode != 0:
            return f"Failed to type text: {result.stderr.strip()}"
        return f"Typed: {text[:80]}{'...' if len(text) > 80 else ''}"
    except Exception as e:
        return f"type_text error: {e}"


def press_key(keys: str) -> str:
    """
    Press a key or keyboard shortcut.

    Examples:
      "return"          — press Enter
      "escape"          — press Escape
      "ctrl+backtick"   — open VS Code integrated terminal
      "ctrl+c"          — interrupt running process
      "ctrl+l"          — clear terminal
      "cmd+k"           — clear terminal (macOS)
      "up"              — arrow up (browse command history)
      "tab"             — autocomplete
    """
    try:
        parts = [p.strip().lower() for p in keys.split("+")]

        modifiers = []
        key_part  = None

        for part in parts:
            if part in _MODIFIER_MAP:
                modifiers.append(_MODIFIER_MAP[part])
            else:
                key_part = part

        if not key_part:
            return f"Could not parse key: '{keys}'"

        using = f" using {{{', '.join(modifiers)}}}" if modifiers else ""

        if key_part in _KEY_CODES:
            action = f"key code {_KEY_CODES[key_part]}{using}"
        else:
            escaped = key_part.replace("\\", "\\\\").replace('"', '\\"')
            action = f'keystroke "{escaped}"{using}'

        script = f'tell application "System Events" to {action}'
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True)

        if result.returncode != 0:
            return f"Failed to press '{keys}': {result.stderr.strip()}"
        return f"Pressed: {keys}"
    except Exception as e:
        return f"press_key error: {e}"


def wait_seconds(seconds: int) -> str:
    """
    Wait for a number of seconds before the next action.
    Use after opening apps, running commands, or any time you need to let
    something load before reading the screen.
    Max 60 seconds.
    """
    seconds = min(max(1, int(seconds)), 60)
    time.sleep(seconds)
    return f"Waited {seconds} second{'s' if seconds != 1 else ''}."
