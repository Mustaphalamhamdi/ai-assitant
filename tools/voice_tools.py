import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def switch_voice(language: str) -> str:
    """Switch Aria's voice to a preset language voice."""
    from config import ELEVENLABS_VOICE_PRESETS
    import speaker.tts as tts

    key = language.lower().strip()

    # Find best matching preset key
    voice_id = None
    for preset_key, vid in ELEVENLABS_VOICE_PRESETS.items():
        if preset_key in key or key in preset_key:
            voice_id = vid
            break

    if not voice_id:
        available = ", ".join(k for k in ELEVENLABS_VOICE_PRESETS if k != "default")
        return f"No voice preset for '{language}'. Available: {available}."

    tts.set_voice_id(voice_id)
    return f"Switched to {language} voice."
