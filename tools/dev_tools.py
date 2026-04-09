import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROJECTS_FOLDER


def _fuzzy_match_project(name: str, folders: list) -> str | None:
    """Find the best folder name match for a (possibly misheard) project name."""
    name_clean = name.lower().replace(" ", "").replace("-", "").replace("_", "")

    # 1. Exact match
    for f in folders:
        if f.lower() == name.lower():
            return f

    # 2. Cleaned exact match
    for f in folders:
        if f.lower().replace(" ", "").replace("-", "").replace("_", "") == name_clean:
            return f

    # 3. Best substring / overlap score
    best, best_score = None, 0.0
    for f in folders:
        f_clean = f.lower().replace(" ", "").replace("-", "").replace("_", "")
        common = sum(1 for a, b in zip(name_clean, f_clean) if a == b)
        score = common / max(len(name_clean), len(f_clean), 1)
        # Boost if one contains the other
        if name_clean in f_clean or f_clean in name_clean:
            score = max(score, min(len(name_clean), len(f_clean)) /
                        max(len(name_clean), len(f_clean)))
        if score > best_score:
            best_score = score
            best = f

    return best if best_score >= 0.5 else None


def open_project(name: str) -> str:
    if not os.path.isdir(PROJECTS_FOLDER):
        return f"Projects folder '{PROJECTS_FOLDER}' not found."

    folders = [f for f in os.listdir(PROJECTS_FOLDER)
               if os.path.isdir(os.path.join(PROJECTS_FOLDER, f))
               and not f.startswith(".")]

    match = _fuzzy_match_project(name, folders)
    if not match:
        sample = ", ".join(folders[:6]) or "none"
        return f"No project matching '{name}' found. Available: {sample}."

    project_path = os.path.join(PROJECTS_FOLDER, match)
    try:
        subprocess.Popen(["code", project_path])
        return f"Opened project '{match}' in VS Code."
    except FileNotFoundError:
        # Try full path to code CLI
        for candidate in ["/usr/local/bin/code", "/opt/homebrew/bin/code",
                          os.path.expanduser("~/.nvm/versions/node/*/bin/code")]:
            import glob as _glob
            for p in _glob.glob(candidate):
                try:
                    subprocess.Popen([p, project_path])
                    return f"Opened project '{match}' in VS Code."
                except Exception:
                    pass
        return f"VS Code 'code' command not found. Project path: {project_path}"
    except Exception as e:
        return f"Failed to open project '{match}': {e}"


def list_projects() -> list:
    """Return list of project folder names (used by the UI dropdown)."""
    if not os.path.isdir(PROJECTS_FOLDER):
        return []
    return sorted(f for f in os.listdir(PROJECTS_FOLDER)
                  if os.path.isdir(os.path.join(PROJECTS_FOLDER, f))
                  and not f.startswith("."))


def run_terminal(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30)
        output = (result.stdout + result.stderr).strip()
        return output[:300] if output else "Command ran with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"
