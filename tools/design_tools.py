import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DESIGN_FOLDER, OS

SUBFOLDERS = ["assets", "exports", "source", "references"]


def create_design_project(name: str) -> str:
    project_path = os.path.join(DESIGN_FOLDER, name)
    try:
        for sub in SUBFOLDERS:
            os.makedirs(os.path.join(project_path, sub), exist_ok=True)
        return f"Design project '{name}' created at {project_path}."
    except Exception as e:
        return f"Failed to create design project '{name}': {e}"


def open_design_folder() -> str:
    try:
        if OS == "Darwin":
            subprocess.Popen(["open", DESIGN_FOLDER])
        else:
            subprocess.Popen(["explorer", DESIGN_FOLDER], shell=True)
        return f"Opened design folder: {DESIGN_FOLDER}"
    except Exception as e:
        return f"Failed to open design folder: {e}"


def move_exports_to_desktop(project_name: str) -> str:
    exports_path = os.path.join(DESIGN_FOLDER, project_name, "exports")
    desktop = os.path.expanduser("~/Desktop")

    if not os.path.exists(exports_path):
        return f"No exports folder found for project '{project_name}'."

    files = [f for f in os.listdir(exports_path) if os.path.isfile(os.path.join(exports_path, f))]
    if not files:
        return f"No files found in exports folder for '{project_name}'."

    copied = []
    for filename in files:
        src = os.path.join(exports_path, filename)
        dst = os.path.join(desktop, filename)
        shutil.copy2(src, dst)
        copied.append(filename)

    return f"Copied {len(copied)} file(s) to Desktop: {', '.join(copied)}"
