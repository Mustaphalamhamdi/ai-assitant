"""
browser_tools.py
Controls Chrome via AppleScript/JavaScript injection.
- play_youtube(query)   : search YouTube and click the first video
- read_screen(question) : screenshot + Groq vision to describe/answer what's on screen
"""
import os
import sys
import subprocess
import tempfile
import time
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_API_KEY, OS


# ── YouTube playback ──────────────────────────────────────────────────────────

_CLICK_FIRST_VIDEO_JS = """
(function() {
    var selectors = [
        'ytd-video-renderer a#video-title',
        'ytd-video-renderer a.yt-simple-endpoint[href*="/watch"]',
        'ytd-rich-item-renderer a#video-title-link',
        'ytd-rich-grid-media a#video-title-link',
        'ytd-compact-video-renderer a#video-title',
        'a#video-title-link[href*="/watch"]',
        'a#video-title[href*="/watch"]',
        'ytd-thumbnail a[href*="/watch"]'
    ];
    for (var i = 0; i < selectors.length; i++) {
        var els = document.querySelectorAll(selectors[i]);
        if (els && els.length > 0) {
            for (var j = 0; j < els.length; j++) {
                var href = els[j].href || '';
                if (href.indexOf('/shorts/') === -1 && href.indexOf('/watch') !== -1) {
                    els[j].click();
                    return 'ok';
                }
            }
        }
    }
    return 'not_found';
})()
"""

_CHROME_JS_SCRIPT = """
tell application "Google Chrome"
    activate
    delay {delay}
    tell front window
        tell active tab
            execute javascript "{js}"
        end tell
    end tell
end tell
"""


def _run_chrome_js(js: str, delay: float = 3.0) -> str:
    if OS != "Darwin":
        return "Browser control only supported on macOS."
    js_escaped = js.replace('"', '\\"').replace("\n", " ")
    script = _CHROME_JS_SCRIPT.format(delay=delay, js=js_escaped)
    result = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=15)
    return result.stdout.strip()


def play_youtube(query: str) -> str:
    """Search YouTube for query and play the first video result."""
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"

    if OS != "Darwin":
        subprocess.Popen(["cmd", "/c", "start", search_url], shell=True)
        return f"Opened YouTube search for {query}."

    # Open in Chrome and bring it to front
    subprocess.Popen(["open", "-a", "Google Chrome", search_url])
    time.sleep(1)
    subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'],
                   capture_output=True, timeout=5)

    # Wait for page and results to fully load
    time.sleep(8)

    # Attempt 1
    result = _run_chrome_js(_CLICK_FIRST_VIDEO_JS, delay=1)
    if "ok" in result:
        return f"Playing {query} on YouTube."

    # Attempt 2 — give YouTube more time
    time.sleep(5)
    result = _run_chrome_js(_CLICK_FIRST_VIDEO_JS, delay=1)
    if "ok" in result:
        return f"Playing {query} on YouTube."

    # JS injection failed — Chrome permission not enabled
    return (
        f"Opened YouTube search for '{query}' but could not click the video automatically. "
        "To fix: open Chrome → View menu → Developer → tick 'Allow JavaScript from Apple Events'. "
        "Do that once and it will auto-play every time."
    )


# ── Spotify playback ─────────────────────────────────────────────────────────

def _spotify_url_to_uri(url: str) -> str | None:
    """Convert https://open.spotify.com/track/ID → spotify:track:ID (strips ?si=...)"""
    import re
    m = re.search(r'open\.spotify\.com/(track|playlist|album|artist)/([A-Za-z0-9]+)', url)
    if m:
        return f"spotify:{m.group(1)}:{m.group(2)}"
    return None


def play_spotify(query: str) -> str:
    """Open Spotify and play a track/playlist by saved name, Spotify URL, URI, or search."""
    if OS != "Darwin":
        return "Spotify control is only supported on macOS."

    def _open_and_play(spotify_uri: str) -> None:
        """Open a Spotify URI and ensure it starts playing."""
        subprocess.Popen(["open", spotify_uri])
        time.sleep(3)
        # AppleScript: activate Spotify and press play in case it paused
        script = """
tell application "Spotify"
    activate
    if player state is not playing then
        play
    end if
end tell
"""
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=8)

    # If query is a Spotify URL, convert and play directly
    uri = _spotify_url_to_uri(query)
    if uri:
        _open_and_play(uri)
        return "Playing on Spotify."

    # If query is already a spotify: URI
    if query.strip().startswith("spotify:"):
        _open_and_play(query.strip())
        return "Playing on Spotify."

    # Check saved playlists/tracks by name
    try:
        from user_config import get_config
        uri = get_config().find_spotify_playlist(query)
        if uri:
            _open_and_play(uri)
            return f"Playing {query} on Spotify."
    except Exception:
        pass

    # Fall back: open Spotify search
    subprocess.Popen(["open", f"spotify:search:{quote_plus(query)}"])
    time.sleep(2)

    # Try AppleScript keyboard automation to play first result
    escaped = query.replace('"', '\\"')
    script = f"""
tell application "Spotify" to activate
delay 1.5
tell application "System Events"
    tell process "Spotify"
        keystroke "k" using command down
        delay 0.8
        keystroke "a" using command down
        delay 0.2
        keystroke "{escaped}"
        delay 0.6
        keystroke return
    end tell
end tell
"""
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=12)
    return f"Searching for {query} on Spotify."


# ── Screen reading ────────────────────────────────────────────────────────────

def read_screen(question: str = "What is on the screen?") -> str:
    """Take a screenshot and answer a question about it using Groq vision."""
    import base64
    from groq import Groq

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        # Use mss for cross-platform capture (avoids screencapture permission issues)
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                monitor = sct.monitors[0]  # all monitors combined
                shot = sct.grab(monitor)
                mss.tools.to_png(shot.rgb, shot.size, output=tmp_path)
        except Exception as mss_err:
            # Fallback to screencapture on macOS
            if OS == "Darwin":
                result = subprocess.run(["screencapture", "-x", tmp_path],
                                        capture_output=True)
                if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                    return "Screen recording permission not granted. Add Terminal to Screen Recording in System Settings → Privacy & Security."
            else:
                return f"Screen capture failed: {mss_err}"

        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type":      "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    },
                    {
                        "type": "text",
                        "text": (
                            f"{question}\n\n"
                            "Be concise — 2-3 sentences max. "
                            "If there are video titles or search results visible, list the first 3."
                        )
                    }
                ]
            }],
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        return f"Could not read screen: {e}"
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
