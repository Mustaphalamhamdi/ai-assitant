#!/usr/bin/env python3
"""
Creates ~/Applications/Aria.app and registers it to auto-start on login.
Run once: python setup_app.py
"""
import os
import stat
import subprocess

PROJECT = os.path.dirname(os.path.abspath(__file__))
PYTHON  = os.path.join(PROJECT, "venv", "bin", "python")
HOME    = os.path.expanduser("~")
APP_DIR = os.path.join(HOME, "Applications")
APP     = os.path.join(APP_DIR, "Aria.app")

os.makedirs(APP_DIR, exist_ok=True)

# ── 1. App bundle structure ───────────────────────────────────────────────────
macos_dir = os.path.join(APP, "Contents", "MacOS")
os.makedirs(macos_dir, exist_ok=True)

# Info.plist — gives the app a proper identity for Accessibility
info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Aria</string>
    <key>CFBundleDisplayName</key>
    <string>Aria</string>
    <key>CFBundleIdentifier</key>
    <string>com.mustapha.aria</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>Aria</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAccessibilityUsageDescription</key>
    <string>Aria needs Accessibility access to type commands and control your computer.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Aria listens for your voice commands.</string>
</dict>
</plist>"""

with open(os.path.join(APP, "Contents", "Info.plist"), "w") as f:
    f.write(info_plist)

# Launcher script — the actual executable inside the bundle
launcher = f"""#!/bin/bash
export HOME="{HOME}"
cd "{PROJECT}"
exec "{PYTHON}" "{PROJECT}/app.py"
"""

launcher_path = os.path.join(macos_dir, "Aria")
with open(launcher_path, "w") as f:
    f.write(launcher)

# Make it executable
current = os.stat(launcher_path).st_mode
os.chmod(launcher_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

print(f"✅  Created {APP}")

# ── 2. LaunchAgent — auto-start on every login ────────────────────────────────
agents_dir = os.path.join(HOME, "Library", "LaunchAgents")
os.makedirs(agents_dir, exist_ok=True)

plist_path = os.path.join(agents_dir, "com.mustapha.aria.plist")

agent_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mustapha.aria</string>
    <key>ProgramArguments</key>
    <array>
        <string>{launcher_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{HOME}/Library/Logs/aria.log</string>
    <key>StandardErrorPath</key>
    <string>{HOME}/Library/Logs/aria_error.log</string>
</dict>
</plist>"""

with open(plist_path, "w") as f:
    f.write(agent_plist)

# Register it so it starts immediately and on every future login
subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
result = subprocess.run(["launchctl", "load",   plist_path],
                        capture_output=True, text=True)

if result.returncode == 0:
    print("✅  Auto-start enabled — Aria launches automatically on every login")
else:
    print(f"⚠️   launchctl: {result.stderr.strip()}")

# ── 3. Instructions ───────────────────────────────────────────────────────────
print()
print("━" * 55)
print("ONE-TIME SETUP — grant Accessibility to Aria:")
print("  System Settings → Privacy & Security → Accessibility")
print("  Click +  →  Go to ~/Applications  →  Add Aria.app")
print("━" * 55)
print()
print("Aria is now running in the background.")
print("To launch it manually: open ~/Applications/Aria.app")
