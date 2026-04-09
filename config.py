import os
import platform

OS = platform.system()  # "Darwin", "Windows", "Linux"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")

# Google Cloud STT — set your API key for much better Moroccan Darija recognition.
# Get a free key: console.cloud.google.com → APIs → Speech-to-Text → Credentials
# Leave empty to use Groq Whisper only.
GOOGLE_STT_API_KEY  = os.environ.get("GOOGLE_STT_API_KEY", "")

# Default voice ID — free built-in ElevenLabs voices (no subscription needed):
#   Arnold (deep male):  VR6AewLTigWG4xSOukaG
#   Adam   (deep male):  pNInz6obpgDQGcFmaJgB
#   Josh   (deep male):  TxGEqnHWrfWFTfGW9XjX
#   Sam    (deep male):  yoZ06aMxZJJ28mfd3POQ
# Library voices require a paid plan — add them to your Voice Lab first to get a free-tier ID.
# Library voices (eadgjmk4R4uojdsheG9t, JTlYtJrcTzPC71hMLOxo) require ElevenLabs Starter ($5/mo).
# Swap ELEVENLABS_VOICE_ID to your library voice ID after upgrading.
# Free fallback: Arnold = VR6AewLTigWG4xSOukaG
ELEVENLABS_VOICE_ID        = "eadgjmk4R4uojdsheG9t"   # English voice (needs paid plan)
ELEVENLABS_ARABIC_VOICE_ID = "PmGnwGtnBs40iau7JfoF"    # Moroccan Darija voice

ELEVENLABS_VOICE_PRESETS = {
    "default":  "eadgjmk4R4uojdsheG9t",
    "english":  "eadgjmk4R4uojdsheG9t",
    "japanese": "JTlYtJrcTzPC71hMLOxo",
    "japan":    "JTlYtJrcTzPC71hMLOxo",
    "jp":       "JTlYtJrcTzPC71hMLOxo",
    # Arabic / Moroccan Darija
    "arabic":   "PmGnwGtnBs40iau7JfoF",
    "darija":   "PmGnwGtnBs40iau7JfoF",
    "moroccan": "PmGnwGtnBs40iau7JfoF",
    "ar":       "PmGnwGtnBs40iau7JfoF",
}

# Free fallback voice used when ElevenLabs returns 402 (library voice / unpaid plan)
ELEVENLABS_FREE_FALLBACK_VOICE_ID = "VR6AewLTigWG4xSOukaG"   # Arnold

if OS == "Darwin":
    APP_PATHS = {
        "vscode": "/Applications/Visual Studio Code.app",
        "vs code": "/Applications/Visual Studio Code.app",
        "code": "/Applications/Visual Studio Code.app",
        "terminal": "/System/Applications/Utilities/Terminal.app",
        "iterm": "/Applications/iTerm.app",
        "iterm2": "/Applications/iTerm.app",
        "docker": "/Applications/Docker.app",
        "postman": "/Applications/Postman.app",
        "chrome": "/Applications/Google Chrome.app",
        "google chrome": "/Applications/Google Chrome.app",
        "firefox": "/Applications/Firefox.app",
        "figma": "/Applications/Figma.app",
        "photoshop": "/Applications/Adobe Photoshop 2024/Adobe Photoshop 2024.app",
        "illustrator": "/Applications/Adobe Illustrator 2024/Adobe Illustrator 2024.app",
        "notion": "/Applications/Notion.app",
        "slack": "/Applications/Slack.app",
        "spotify": "/Applications/Spotify.app",
    }
    PROJECTS_FOLDER = os.path.expanduser("~/projects")
    DESIGN_FOLDER = os.path.expanduser("~/Design")
else:
    APP_PATHS = {
        "vscode": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "vs code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "terminal": r"C:\Windows\System32\cmd.exe",
        "iterm": r"C:\Windows\System32\cmd.exe",
        "iterm2": r"C:\Windows\System32\cmd.exe",
        "docker": r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
        "postman": r"C:\Users\%USERNAME%\AppData\Local\Postman\Postman.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "figma": r"C:\Users\%USERNAME%\AppData\Local\Figma\Figma.exe",
        "photoshop": r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
        "illustrator": r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
        "notion": r"C:\Users\%USERNAME%\AppData\Local\Programs\Notion\Notion.exe",
        "slack": r"C:\Users\%USERNAME%\AppData\Local\slack\slack.exe",
        "spotify": r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe",
    }
    PROJECTS_FOLDER = os.path.expanduser("~/projects")
    DESIGN_FOLDER = os.path.expanduser("~/Design")
