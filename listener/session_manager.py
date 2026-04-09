import threading
from listener.stt import transcribe
from speaker.tts import speak

SESSION_TIMEOUT = 300  # 5 minutes


class SessionManager:
    def __init__(self, on_command_callback):
        self._callback = on_command_callback
        self._active = False
        self._timer = None

    def start(self):
        self._active = True
        self._reset_timer()
        self._listen_loop()

    def _reset_timer(self):
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(SESSION_TIMEOUT, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _on_timeout(self):
        self._active = False
        speak("Going to sleep")

    def _listen_loop(self):
        silence_count = 0
        MAX_SILENCE   = 3   # end session after 3 consecutive empty captures

        while self._active:
            text = transcribe()
            if not self._active:
                break
            if text:
                silence_count = 0
                self._reset_timer()
                try:
                    result = self._callback(text)
                    if result is False:   # dismiss signal
                        self._active = False
                        break
                except Exception as e:
                    speak(f"Sorry, something went wrong: {e}")
            else:
                silence_count += 1
                if silence_count >= MAX_SILENCE:
                    self._active = False
                    speak("Going to sleep.")

        if self._timer is not None:
            self._timer.cancel()
