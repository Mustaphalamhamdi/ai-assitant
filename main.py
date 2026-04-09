import time

from speaker.tts import speak, speak_male
from brain.gemini_agent import ask_gemini
from listener.wake_detector import listen_for_wake_word
from listener.session_manager import SessionManager
from tools.app_control import open_app, close_app
from tools.dev_tools import open_project, run_terminal
from tools.design_tools import create_design_project, open_design_folder, move_exports_to_desktop
from tools.web_tools import open_url, search_web
from tools.productivity_tools import (
    take_screenshot,
    read_clipboard,
    control_volume,
    start_focus_timer,
    remind_me,
)

TOOL_MAP = {
    "open_app": open_app,
    "close_app": close_app,
    "open_project": open_project,
    "run_terminal": run_terminal,
    "create_design_project": create_design_project,
    "open_design_folder": open_design_folder,
    "move_exports_to_desktop": move_exports_to_desktop,
    "search_web": search_web,
    "open_url": open_url,
    "take_screenshot": take_screenshot,
    "read_clipboard": read_clipboard,
    "control_volume": control_volume,
    "start_focus_timer": start_focus_timer,
    "remind_me": remind_me,
}


def on_command(text: str) -> None:
    if not text.strip():
        return

    print(f"👤 You: {text}")
    result = ask_gemini(text)

    if result["type"] == "tool":
        action = result.get("action", "")
        params = result.get("params", {})
        tool_fn = TOOL_MAP.get(action)

        if tool_fn is None:
            speak(f"I don't have a tool called {action}.")
            return

        try:
            tool_result = tool_fn(**params)
            speak(tool_result)
        except Exception as e:
            speak(f"The tool ran into a problem: {e}")

    elif result["type"] == "speech":
        speak(result.get("text", ""))


def on_wake() -> None:
    speak_male("Hey Sir, what can I do for you?")
    session = SessionManager(on_command)
    session.start()


if __name__ == "__main__":
    print("🤖 Aria is ready. Say 'Wake up MotherFucker' to activate.")
    while True:
        try:
            listen_for_wake_word()
            on_wake()
        except KeyboardInterrupt:
            print("\nAria signing off. Goodbye!")
            break
        except Exception as e:
            print(f"⚠️  Error: {e}. Restarting listener...")
            time.sleep(1)
