import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("--- TTS Test ---")
from speaker.tts import speak
speak("Hello! I am Aria, your assistant. How are you doing?")

print("\n--- STT Test ---")
print("Say something after the prompt...")
from listener.stt import transcribe
text = transcribe()
speak(f"I heard you say: {text}")

print("\nTest complete!")
