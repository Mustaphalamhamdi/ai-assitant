import time

from speaker.tts import speak, speak_male
from brain.gemini_agent import ask_gemini, reset_conversation
from listener.wake_detector import listen_for_wake_word
from listener.session_manager import SessionManager
from tools.app_control import open_app, close_app
from tools.dev_tools import open_project, run_terminal
from tools.design_tools import create_design_project, open_design_folder, move_exports_to_desktop
from tools.web_tools import open_url, search_web
from tools.browser_tools import play_youtube, play_spotify, read_screen
from tools.productivity_tools import (
    take_screenshot,
    read_clipboard,
    control_volume,
    start_focus_timer,
    remind_me,
)
from tools.voice_tools import switch_voice
from tools.control_tools import type_text, press_key, wait_seconds

TOOL_MAP = {
    "open_app": open_app, "close_app": close_app,
    "open_project": open_project, "run_terminal": run_terminal,
    "create_design_project": create_design_project,
    "open_design_folder": open_design_folder,
    "move_exports_to_desktop": move_exports_to_desktop,
    "search_web": search_web, "open_url": open_url,
    "play_youtube": play_youtube, "play_spotify": play_spotify, "read_screen": read_screen,
    "take_screenshot": take_screenshot, "read_clipboard": read_clipboard,
    "control_volume": control_volume, "start_focus_timer": start_focus_timer,
    "remind_me": remind_me,
    "switch_voice": switch_voice,
    "type_text": type_text,
    "press_key": press_key,
    "wait_seconds": wait_seconds,
}


def _tool_executor(action: str, params: dict) -> str:
    fn = TOOL_MAP.get(action)
    if fn is None:
        return f"No tool named '{action}'."
    try:
        return fn(**params)
    except Exception as e:
        return f"Tool error: {e}"


def _intermediate_speak(text: str) -> None:
    print(f"[status] {text}")
    speak(text)


def on_command(text: str) -> None:
    if not text.strip():
        return

    print(f"👤 You: {text}")
    final_text = ask_gemini(text, _tool_executor, speak_fn=_intermediate_speak)
    speak(final_text)


def on_wake() -> None:
    reset_conversation()
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
