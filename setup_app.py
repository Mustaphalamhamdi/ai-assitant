#!/usr/bin/env python3
"""
Creates /Applications/Aria.app and registers it to auto-start on login.
Run once: python setup_app.py
"""
import os
import subprocess
import shutil
import tempfile

PROJECT = os.path.dirname(os.path.abspath(__file__))
PYTHON  = "/opt/anaconda3/bin/python3"
HOME    = os.path.expanduser("~")
APP_DIR = "/Applications"
APP     = os.path.join(APP_DIR, "Aria.app")

os.makedirs(APP_DIR, exist_ok=True)

# ── 1. App bundle structure ───────────────────────────────────────────────────
macos_dir     = os.path.join(APP, "Contents", "MacOS")
resources_dir = os.path.join(APP, "Contents", "Resources")
os.makedirs(macos_dir,     exist_ok=True)
os.makedirs(resources_dir, exist_ok=True)

# Info.plist
info_plist = """<?xml version="1.0" encoding="UTF-8"?>
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
    <key>CFBundleIconFile</key>
    <string>aria</string>
    <key>NSAccessibilityUsageDescription</key>
    <string>Aria needs Accessibility access to type commands and control your computer.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Aria listens for your voice commands.</string>
</dict>
</plist>"""

with open(os.path.join(APP, "Contents", "Info.plist"), "w") as f:
    f.write(info_plist)

# Icon
icon_src = os.path.join(PROJECT, "aria.icns")
if os.path.exists(icon_src):
    shutil.copy2(icon_src, os.path.join(resources_dir, "aria.icns"))

# ── 2. Compile a real binary launcher (shell scripts are blocked on modern macOS) ──
launcher_path = os.path.join(macos_dir, "Aria")

c_src = f"""
#include <stdlib.h>
#include <unistd.h>

int main(void) {{
    setenv("HOME", "{HOME}", 1);
    chdir("{PROJECT}");
    return execl(
        "{PYTHON}",
        "{PYTHON}",
        "{PROJECT}/app.py",
        NULL
    );
}}
"""

c_file = os.path.join(tempfile.gettempdir(), "aria_launcher.c")
with open(c_file, "w") as f:
    f.write(c_src)

result = subprocess.run(
    ["gcc", "-o", launcher_path, c_file],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"❌ Compile failed: {result.stderr}")
    exit(1)

# Ad-hoc sign so macOS trusts it
subprocess.run(["codesign", "--force", "--deep", "--sign", "-", APP],
               capture_output=True)
subprocess.run(["xattr", "-cr", APP], capture_output=True)

print(f"✅  Created {APP}")

# ── 3. LaunchAgent — auto-start on every login ────────────────────────────────
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

subprocess.run(["launchctl", "unload", plist_path], capture_output=True)
result = subprocess.run(["launchctl", "load", plist_path],
                        capture_output=True, text=True)

if result.returncode == 0:
    print("✅  Auto-start enabled — Aria launches on every login")
else:
    print(f"⚠️   launchctl: {result.stderr.strip()}")

print()
print("━" * 55)
print("NEXT: grant Accessibility to Aria.app")
print("  System Settings → Privacy & Security → Accessibility")
print("  Click +  →  /Applications  →  Aria.app")
print("━" * 55)
