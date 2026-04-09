"""
TTS — Text to Speech
Arabic/Darija : Microsoft Edge TTS  → ar-MA-JamalNeural (Moroccan Arabic, natural)
English/other : ElevenLabs          → gTTS → macOS say
"""
import os
import sys
import subprocess
import tempfile
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
                    ELEVENLABS_FREE_FALLBACK_VOICE_ID, ELEVENLABS_ARABIC_VOICE_ID)

# ── Active voice ──────────────────────────────────────────────────────────────
_active_voice_id: str = ELEVENLABS_VOICE_ID

def set_voice_id(voice_id: str) -> None:
    global _active_voice_id
    _active_voice_id = voice_id

def get_voice_id() -> str:
    return _active_voice_id

# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_arabic(text: str) -> bool:
    return any('\u0600' <= c <= '\u06FF' for c in text)


def _play_mp3(path: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["afplay", path], check=True)
    elif sys.platform == "win32":
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            f"(New-Object Media.SoundPlayer '{path}').PlaySync()"
        ], check=True)
    else:
        subprocess.run(["mpg123", "-q", path], check=True)


def _after_speak() -> None:
    from listener.stt import mark_tts_done
    mark_tts_done()


# ── Microsoft Edge TTS (Moroccan Arabic neural voice) ────────────────────────
# Voices: ar-MA-JamalNeural (male), ar-MA-MounaNeural (female)
EDGE_ARABIC_VOICE = "ar-MA-JamalNeural"


def _speak_edge(text: str, voice: str = EDGE_ARABIC_VOICE) -> None:
    """Use edge-tts for human-quality Moroccan Arabic voice."""
    import edge_tts   # pip install edge-tts

    async def _run():
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)
        return tmp_path

    tmp_path = asyncio.run(_run())
    try:
        _play_mp3(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── ElevenLabs ────────────────────────────────────────────────────────────────
_eleven_client = None

def _get_eleven():
    global _eleven_client
    if _eleven_client is None:
        from elevenlabs.client import ElevenLabs
        _eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _eleven_client


def _speak_elevenlabs(text: str, voice_id: str = None) -> None:
    vid = voice_id or _active_voice_id
    try:
        chunks = _get_eleven().text_to_speech.convert(
            text         = text,
            voice_id     = vid,
            model_id     = "eleven_turbo_v2_5",
            output_format= "mp3_44100_128",
        )
        audio = b"".join(chunks)
    except Exception as e:
        if "402" in str(e) or "payment_required" in str(e):
            if vid != ELEVENLABS_FREE_FALLBACK_VOICE_ID:
                print("⚠️  Library voice needs paid plan, using free fallback…")
                _speak_elevenlabs(text, voice_id=ELEVENLABS_FREE_FALLBACK_VOICE_ID)
                return
        raise

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with open(tmp_path, "wb") as f:
        f.write(audio)
    try:
        _play_mp3(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Fallbacks ─────────────────────────────────────────────────────────────────
def _speak_google(text: str) -> None:
    from gtts import gTTS
    lang = "ar" if _is_arabic(text) else "en"
    tts = gTTS(text=text, lang=lang, slow=False)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()
    tts.save(tmp_path)
    try:
        _play_mp3(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _speak_system(text: str) -> None:
    if sys.platform == "darwin":
        voice = "Tarik" if _is_arabic(text) else "Samantha"
        subprocess.run(["say", "-v", voice, text])
    else:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.say(text)
        engine.runAndWait()


# ── Core dispatch ─────────────────────────────────────────────────────────────
def _speak(text: str) -> None:
    arabic = _is_arabic(text)
    has_key = "YOUR_ELEVENLABS_KEY_HERE" not in ELEVENLABS_API_KEY

    if arabic and has_key and ELEVENLABS_ARABIC_VOICE_ID:
        # Dedicated Arabic/Darija ElevenLabs voice chosen by user
        try:
            _speak_elevenlabs(text, voice_id=ELEVENLABS_ARABIC_VOICE_ID)
            _after_speak()
            return
        except Exception as e:
            print(f"⚠️  ElevenLabs Arabic voice failed ({e}), trying Edge TTS…")

    if arabic:
        # Edge TTS Moroccan Arabic neural voice (free, no key needed)
        try:
            _speak_edge(text, voice=EDGE_ARABIC_VOICE)
            _after_speak()
            return
        except Exception as e:
            print(f"⚠️  Edge TTS failed ({e}), falling back to system voice…")
            _speak_system(text)   # macOS say -v Tarik
            _after_speak()
            return

    # English / other → ElevenLabs → gTTS → system
    if has_key:
        try:
            _speak_elevenlabs(text)
            _after_speak()
            return
        except Exception as e:
            print(f"⚠️  ElevenLabs failed ({e}), trying gTTS…")

    try:
        _speak_google(text)
    except Exception as e:
        print(f"⚠️  gTTS failed ({e}), using system voice…")
        _speak_system(text)
    _after_speak()


# ── Public API ────────────────────────────────────────────────────────────────
def speak_male(text: str) -> None:
    print(f"🤖 Aria: {text}")
    _speak(text)

def speak(text: str, online: bool = True) -> None:
    print(f"🤖 Aria: {text}")
    _speak(text)
