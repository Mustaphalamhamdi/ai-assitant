"""
user_config.py — persists user-defined workflows and custom apps to user_config.json
"""
import json
import os
import uuid
import threading

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")

_DEFAULT: dict = {"workflows": [], "custom_apps": [], "spotify_playlists": []}

# ── Singleton ─────────────────────────────────────────────────────────────────
_instance = None
_lock = threading.Lock()


def get_config() -> "UserConfig":
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = UserConfig()
    return _instance


# ── Config class ──────────────────────────────────────────────────────────────

class UserConfig:
    def __init__(self):
        self._data: dict = {"workflows": [], "custom_apps": []}
        self._load()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    loaded = json.load(f)
                self._data.update(loaded)
            except Exception:
                pass

    def save(self) -> None:
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    # ── workflows ─────────────────────────────────────────────────────────────

    @property
    def workflows(self) -> list:
        return self._data.setdefault("workflows", [])

    def add_workflow(self, name: str, trigger: str, steps: list) -> dict:
        wf = {"id": str(uuid.uuid4()), "name": name, "trigger": trigger, "steps": steps}
        self.workflows.append(wf)
        self.save()
        return wf

    def update_workflow(self, wf_id: str, name: str, trigger: str, steps: list) -> None:
        for wf in self.workflows:
            if wf["id"] == wf_id:
                wf["name"]    = name
                wf["trigger"] = trigger
                wf["steps"]   = steps
                self.save()
                return

    def delete_workflow(self, wf_id: str) -> None:
        self._data["workflows"] = [w for w in self.workflows if w["id"] != wf_id]
        self.save()

    def find_matching_workflow(self, command: str) -> dict | None:
        """Return the best-matching workflow for a voice command, or None."""
        cmd_words = set(command.lower().split())
        best, best_score = None, 0.0
        for wf in self.workflows:
            trigger_words = wf["trigger"].lower().split()
            if not trigger_words:
                continue
            hits = sum(1 for w in trigger_words if w in cmd_words)
            score = hits / len(trigger_words)
            if score >= 0.7 and score > best_score:
                best_score = score
                best = wf
        return best

    # ── custom apps ───────────────────────────────────────────────────────────

    @property
    def custom_apps(self) -> list:
        return self._data.setdefault("custom_apps", [])

    def add_app(self, name: str, triggers: str, path: str) -> dict:
        """triggers: comma-separated list of voice keywords"""
        app = {"id": str(uuid.uuid4()), "name": name, "triggers": triggers, "path": path}
        self.custom_apps.append(app)
        self.save()
        return app

    def update_app(self, app_id: str, name: str, triggers: str, path: str) -> None:
        for app in self.custom_apps:
            if app["id"] == app_id:
                app["name"]     = name
                app["triggers"] = triggers
                app["path"]     = path
                self.save()
                return

    def delete_app(self, app_id: str) -> None:
        self._data["custom_apps"] = [a for a in self.custom_apps if a["id"] != app_id]
        self.save()

    # ── spotify playlists ─────────────────────────────────────────────────────

    @property
    def spotify_playlists(self) -> list:
        return self._data.setdefault("spotify_playlists", [])

    def add_spotify_playlist(self, name: str, uri: str) -> dict:
        entry = {"id": str(uuid.uuid4()), "name": name, "uri": uri}
        self.spotify_playlists.append(entry)
        self.save()
        return entry

    def delete_spotify_playlist(self, entry_id: str) -> None:
        self._data["spotify_playlists"] = [p for p in self.spotify_playlists if p["id"] != entry_id]
        self.save()

    def find_spotify_playlist(self, query: str) -> str | None:
        """Return Spotify URI for a playlist matching the query, or None."""
        q = query.lower().strip()
        for p in self.spotify_playlists:
            if q == p["name"].lower():
                return p["uri"]
        for p in self.spotify_playlists:
            if q in p["name"].lower() or p["name"].lower() in q:
                return p["uri"]
        return None

    def get_app_paths(self) -> dict:
        """Return a dict of {trigger_key: path} for all custom apps."""
        result = {}
        for app in self.custom_apps:
            for key in [k.strip().lower() for k in app["triggers"].split(",")]:
                if key:
                    result[key] = app["path"]
        return result
