import subprocess
import os
import sys
import glob
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import APP_PATHS, OS

# ── AppleScript that clicks "Allow" / "OK" on macOS permission dialogs ────────
_ALLOW_SCRIPT = """
tell application "System Events"
    repeat with proc in every process
        try
            tell proc
                repeat with w in every window
                    try
                        if exists button "Allow" of w then
                            click button "Allow" of w
                        end if
                    end try
                    try
                        if exists button "OK" of w then
                            click button "OK" of w
                        end if
                    end try
                end repeat
            end tell
        end try
    end repeat
end tell
"""


def _auto_allow_watcher(duration: int = 35) -> None:
    """Poll for macOS permission dialogs and click Allow for `duration` seconds."""
    deadline = time.time() + duration
    while time.time() < deadline:
        try:
            subprocess.run(
                ["osascript", "-e", _ALLOW_SCRIPT],
                capture_output=True, timeout=4,
            )
        except Exception:
            pass
        time.sleep(1.5)


_global_watcher_started = False

def start_global_allow_watcher() -> None:
    """Start a persistent background thread that auto-clicks Allow dialogs indefinitely."""
    global _global_watcher_started
    if _global_watcher_started:
        return
    _global_watcher_started = True

    def _loop():
        while True:
            try:
                subprocess.run(
                    ["osascript", "-e", _ALLOW_SCRIPT],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass
            time.sleep(2)

    threading.Thread(target=_loop, daemon=True, name="allow-watcher").start()


def _resolve_path(path: str) -> str:
    """If the exact path doesn't exist, try to find it by glob (handles year variants)."""
    if os.path.exists(path):
        return path
    # Strip year number and glob — e.g. "Adobe Illustrator 2024" → "Adobe Illustrator*"
    import re
    base_dir  = os.path.dirname(path)          # /Applications/Adobe Illustrator 2024
    app_file  = os.path.basename(path)          # Adobe Illustrator 2024.app
    # Remove trailing year from folder name
    parent_glob = re.sub(r'\s+\d{4}$', '*', base_dir)
    app_glob    = re.sub(r'\s+\d{4}', '*', app_file)
    matches = sorted(glob.glob(os.path.join(parent_glob, app_glob)), reverse=True)
    return matches[0] if matches else path


def open_app(name: str) -> str:
    # Merge built-in paths with user-defined custom apps
    try:
        from user_config import get_config
        merged = {**APP_PATHS, **get_config().get_app_paths()}
    except Exception:
        merged = APP_PATHS

    key = name.lower().strip()
    path = merged.get(key)

    if not path:
        # Partial match in the table
        for k, v in APP_PATHS.items():
            if key in k or k in key:
                path = v
                break

    if not path:
        # Last resort: scan /Applications for anything matching the name
        if OS == "Darwin":
            keyword = key.split()[0].capitalize()
            candidates = glob.glob(f"/Applications/**/{keyword}*.app", recursive=True)
            candidates += glob.glob(f"/Applications/{keyword}*.app")
            if candidates:
                path = sorted(candidates, reverse=True)[0]

    if not path:
        return f"I don't know how to open '{name}'. You can add it to APP_PATHS in config.py."

    path = _resolve_path(path)

    try:
        if OS == "Darwin":
            subprocess.Popen(["open", path])
            # Watch for and auto-accept permission dialogs (folder access, etc.)
            t = threading.Thread(target=_auto_allow_watcher, daemon=True)
            t.start()
        else:
            subprocess.Popen([os.path.expandvars(path)], shell=True)
        return f"Opening {name}."
    except Exception as e:
        return f"Failed to open {name}: {e}"


def close_app(name: str) -> str:
    app_name = name.strip()
    try:
        if OS == "Darwin":
            subprocess.run(
                ["pkill", "-f", app_name],
                capture_output=True,
            )
        else:
            subprocess.run(
                ["taskkill", "/F", "/IM", f"{app_name}.exe"],
                capture_output=True,
                shell=True,
            )
        return f"Closed {name}."
    except Exception as e:
        return f"Failed to close {name}: {e}"
