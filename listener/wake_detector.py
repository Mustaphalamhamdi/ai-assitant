"""
wake_detector.py
Wakes Aria on either:
  • Voice: say "Wake up MotherFucker" (or any WAKE_PHRASES word)
  • Claps: two sharp claps within 1.5 seconds
Single audio stream feeds both detectors — no concurrent PyAudio conflict.
"""
import time
import numpy as np
import pyaudio
import speech_recognition as sr

# ── Voice wake phrases ────────────────────────────────────────────────────────
WAKE_PHRASES = [
    # English
    "wake up", "wake", "motherfucker", "wakeup", "mother",
    # Arabic / Moroccan Darija
    "aria", "arya", "صحى", "فيق", "فيقي", "هدر", "سولي", "واش راك",
]

_recognizer = sr.Recognizer()

# ── Clap-detection tuning ─────────────────────────────────────────────────────
CLAP_PEAK_THRESHOLD = 2500
CLAP_SPIKE_RATIO    = 4.0
CLAP_MIN_GAP        = 0.15
CLAP_MAX_GAP        = 1.4
CLAP_CHUNK          = 512

# ── Speech buffer: accumulate 3 s then run recognition ───────────────────────
SPEECH_WINDOW_SEC   = 3.0
SPEECH_OVERLAP_SEC  = 0.5


def listen_for_wake_word() -> None:
    """Block until wake word OR double-clap is detected."""
    print("👂 Waiting for wake word  or  👏👏 two claps …")

    pa     = pyaudio.PyAudio()
    stream = pa.open(
        format           = pyaudio.paInt16,
        channels         = 1,
        rate             = 16000,
        input            = True,
        frames_per_buffer= CLAP_CHUNK,
    )

    clap_times:   list  = []
    prev_peak:    float = 0.0
    speech_buf:   list  = []          # raw bytes
    buf_duration: float = 0.0         # seconds accumulated

    chunk_dur = CLAP_CHUNK / 16000    # seconds per chunk

    try:
        while True:
            try:
                data = stream.read(CLAP_CHUNK, exception_on_overflow=False)
            except Exception:
                time.sleep(0.01)
                continue

            chunk = np.frombuffer(data, dtype=np.int16)

            # ── Clap detection ────────────────────────────────────────────────
            peak = float(np.abs(chunk).max())
            if peak > CLAP_PEAK_THRESHOLD and (prev_peak < 1 or peak / prev_peak >= CLAP_SPIKE_RATIO):
                now = time.time()
                clap_times = [t for t in clap_times if now - t <= CLAP_MAX_GAP + 0.1]
                clap_times.append(now)
                print(f"[wake/clap] spike  peak={peak:.0f}  count={len(clap_times)}")

                if len(clap_times) >= 2:
                    gaps = [clap_times[i+1] - clap_times[i]
                            for i in range(len(clap_times) - 1)]
                    if any(CLAP_MIN_GAP <= g <= CLAP_MAX_GAP for g in gaps):
                        print("[wake] clap trigger fired")
                        return
                time.sleep(0.08)

            prev_peak = peak

            # ── Speech buffering ──────────────────────────────────────────────
            speech_buf.append(data)
            buf_duration += chunk_dur

            if buf_duration >= SPEECH_WINDOW_SEC:
                audio_data = sr.AudioData(b"".join(speech_buf), 16000, 2)
                try:
                    text = _recognizer.recognize_google(audio_data).lower()
                    print(f"[wake/voice] heard: '{text}'")
                    if any(phrase in text for phrase in WAKE_PHRASES):
                        print("[wake] voice trigger fired")
                        return
                except Exception:
                    pass

                # Keep a short overlap so wake word isn't split across windows
                overlap_chunks = int(SPEECH_OVERLAP_SEC / chunk_dur)
                speech_buf   = speech_buf[-overlap_chunks:]
                buf_duration = overlap_chunks * chunk_dur

    finally:
        try:
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception:
            pass
