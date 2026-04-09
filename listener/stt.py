"""
STT — Speech to Text
Records from mic, uses Groq Whisper large-v3-turbo with confidence filtering
to reject hallucinated transcriptions from background noise / TV.
"""
import pyaudio
import wave
import tempfile
import os
import time
import numpy as np
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GROQ_API_KEY, GOOGLE_STT_API_KEY

CHUNK             = 1024
FORMAT            = pyaudio.paInt16
CHANNELS          = 1
RATE              = 16000
RECORD_SECONDS    = 7
SILENCE_THRESHOLD = 180   # mean energy to count as "speech started"
SILENCE_CHUNKS    = 15    # consecutive quiet chunks before stopping
MIN_SPEECH_ENERGY = 100   # whole-clip mean energy gate

# Confidence thresholds (Whisper verbose_json)
NO_SPEECH_REJECT  = 0.50  # reject if avg no_speech_prob exceeds this
AVG_LOGPROB_FLOOR = -0.85 # reject if avg log-probability is below this (hallucination)

# ── Groq client (lazy) ────────────────────────────────────────────────────────
_groq_client = None

def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


# ── TTS echo suppression ──────────────────────────────────────────────────────
_tts_finished_at: float = 0.0

def mark_tts_done() -> None:
    global _tts_finished_at
    _tts_finished_at = time.time()


def _seg_val(seg, key: str, default=0.0) -> float:
    """Get a value from a segment whether it's a dict or an object."""
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def transcribe() -> str:
    # Wait after TTS ends to avoid echo
    since_tts = time.time() - _tts_finished_at
    if since_tts < 1.0:
        time.sleep(1.0 - since_tts)

    print("🎙️  Listening... speak now")
    pa          = pyaudio.PyAudio()
    sample_size = pa.get_sample_size(FORMAT)
    stream      = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                          input=True, frames_per_buffer=CHUNK)

    frames: list     = []
    silent_chunks    = 0
    max_chunks       = int(RATE / CHUNK * RECORD_SECONDS)
    started_speaking = False

    for _ in range(max_chunks):
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
        except Exception:
            break
        frames.append(data)
        energy = np.abs(np.frombuffer(data, dtype=np.int16)).mean()

        if energy > SILENCE_THRESHOLD:
            started_speaking = True
            silent_chunks    = 0
        elif started_speaking:
            silent_chunks += 1
            if silent_chunks >= SILENCE_CHUNKS:
                break

    stream.stop_stream()
    stream.close()
    pa.terminate()

    # ── Hard gates ────────────────────────────────────────────────────────────
    if not started_speaking or not frames:
        return ""
    raw = np.frombuffer(b"".join(frames), dtype=np.int16)
    if np.abs(raw).mean() < MIN_SPEECH_ENERGY:
        return ""

    audio_bytes = b"".join(frames)

    # ── Try Google STT first (ar-MA = Moroccan Arabic — best for Darija) ─────
    if GOOGLE_STT_API_KEY:
        text = _transcribe_google(audio_bytes)
        if text:
            print(f"[stt/google] heard: '{text}'")
            return text
        print("[stt/google] empty — falling back to Groq")

    # ── Fall back to Groq Whisper ─────────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(sample_size)
            wf.setframerate(RATE)
            wf.writeframes(audio_bytes)

        with open(tmp_path, "rb") as f:
            result = _get_groq().audio.transcriptions.create(
                file            = (os.path.basename(tmp_path), f.read()),
                model           = "whisper-large-v3",
                response_format = "verbose_json",
                prompt          = "المتكلم يتحدث بالدارجة المغربية أو الإنجليزية أو الفرنسية.",
            )

        segments = getattr(result, "segments", None) or []
        if segments:
            no_sp = [_seg_val(s, "no_speech_prob") for s in segments]
            logps = [_seg_val(s, "avg_logprob")    for s in segments]
            avg_no_speech = sum(no_sp) / len(no_sp)
            avg_logprob   = sum(logps) / len(logps)
            if avg_no_speech > NO_SPEECH_REJECT:
                print(f"[stt] rejected — no_speech={avg_no_speech:.2f}")
                return ""
            if avg_logprob < AVG_LOGPROB_FLOOR:
                print(f"[stt] rejected — low confidence logprob={avg_logprob:.2f}")
                return ""

        text = getattr(result, "text", "") or ""
        text = text.strip()
        if text:
            print(f"[stt/groq] heard: '{text}'")
        return text

    except Exception as e:
        print(f"[stt] Groq transcription failed: {e}")
        return ""
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _transcribe_google(audio_bytes: bytes) -> str:
    """Transcribe using Google Cloud STT with ar-MA (Moroccan Arabic) locale."""
    import base64, requests as _req
    audio_b64 = base64.b64encode(audio_bytes).decode()
    payload = {
        "config": {
            "encoding":            "LINEAR16",
            "sampleRateHertz":     RATE,
            "languageCode":        "ar-MA",          # Moroccan Arabic
            "alternativeLanguageCodes": ["en-US", "fr-FR"],  # Darija mixes all three
            "model":               "latest_long",
            "useEnhanced":         True,
            "enableAutomaticPunctuation": False,
        },
        "audio": {"content": audio_b64},
    }
    try:
        resp = _req.post(
            f"https://speech.googleapis.com/v1/speech:recognize?key={GOOGLE_STT_API_KEY}",
            json=payload, timeout=15,
        )
        data = resp.json()
        results = data.get("results", [])
        if results:
            return results[0]["alternatives"][0]["transcript"].strip()
        return ""
    except Exception as e:
        print(f"[stt/google] error: {e}")
        return ""
