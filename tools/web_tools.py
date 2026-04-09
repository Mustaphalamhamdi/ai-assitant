import subprocess
import sys
import os
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OS

QUICK_URLS = {
    "mdn": "https://developer.mozilla.org",
    "mdn docs": "https://developer.mozilla.org",
    "figma docs": "https://help.figma.com",
    "figma": "https://www.figma.com",
    "github": "https://github.com",
    "dribbble": "https://dribbble.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "caniuse": "https://caniuse.com",
    "tailwind": "https://tailwindcss.com/docs",
    "tailwind docs": "https://tailwindcss.com/docs",
    "react": "https://react.dev",
    "react docs": "https://react.dev",
}


_BROWSER_APPS = {
    "chrome":  "Google Chrome",
    "firefox": "Firefox",
    "safari":  "Safari",
    "edge":    "Microsoft Edge",
    "brave":   "Brave Browser",
}


def open_url(url: str, browser: str = None) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        key = url.lower().strip()
        if key in QUICK_URLS:
            url = QUICK_URLS[key]
        else:
            url = "https://" + url

    try:
        if OS == "Darwin":
            if browser:
                app = _BROWSER_APPS.get(browser.lower().strip(), browser)
                subprocess.run(["open", "-a", app, url])
            else:
                subprocess.run(["open", url])
        else:
            subprocess.run(["cmd", "/c", "start", url], shell=True)
        # Speak only the site name, not the full URL
        from urllib.parse import urlparse
        site = urlparse(url).netloc.replace("www.", "")
        return f"Opening {site}."
    except Exception as e:
        return f"Failed to open URL: {e}"


def search_web(query: str) -> str:
    encoded = quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    try:
        if OS == "Darwin":
            subprocess.run(["open", url])
        else:
            subprocess.run(["cmd", "/c", "start", url], shell=True)
        return f"Searching for {query}."
    except Exception as e:
        return f"Failed to search: {e}"
