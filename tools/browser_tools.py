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

def _get_first_youtube_video_id(query: str) -> str | None:
    """
    Fetch YouTube search results server-side and extract the first non-Shorts video ID.
    No browser permissions needed — pure HTTP request + regex.
    """
    import urllib.request
    import re

    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8")
    except Exception:
        return None

    # Primary: watchEndpoint video IDs (organic search results, not ads)
    matches = re.findall(r'"watchEndpoint"[^}]*?"videoId":"([a-zA-Z0-9_-]{11})"', html)
    if matches:
        return matches[0]

    # Fallback: any videoId in the page
    matches = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    return matches[0] if matches else None


def play_youtube(query: str) -> str:
    """Search YouTube and open the first video result directly in Chrome. No permissions needed."""
    if OS != "Darwin":
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        subprocess.Popen(["cmd", "/c", "start", url], shell=True)
        return f"Opened YouTube search for {query}."

    video_id = _get_first_youtube_video_id(query)
    if video_id:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        subprocess.Popen(["open", "-a", "Google Chrome", video_url])
        return f"Playing {query} on YouTube."

    # Fallback: open search page
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    subprocess.Popen(["open", "-a", "Google Chrome", search_url])
    return f"Opened YouTube search for '{query}'."


def close_tab() -> str:
    """Close the active tab in Chrome using Chrome's native AppleScript (no Accessibility needed)."""
    if OS != "Darwin":
        return "Tab control only supported on macOS."
    script = """
tell application "Google Chrome"
    if (count of windows) > 0 then
        close active tab of front window
    end if
end tell
"""
    result = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        return "Closed the active tab."
    return f"Could not close tab: {result.stderr.strip()}"


def _run_chrome_js(js: str, delay: float = 1.0) -> str:
    """Execute JavaScript in Chrome's active tab via AppleScript (requires Allow JS from Apple Events)."""
    if OS != "Darwin":
        return "Browser JS control only supported on macOS."
    js_escaped = js.replace('"', '\\"').replace("\n", " ")
    script = f"""tell application "Google Chrome"
    activate
    delay {delay}
    tell front window
        tell active tab
            execute javascript "{js_escaped}"
        end tell
    end tell
end tell"""
    result = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=15)
    return result.stdout.strip()


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
