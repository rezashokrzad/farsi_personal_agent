import json
import time
import subprocess
from vosk import Model, KaldiRecognizer, SetLogLevel

SetLogLevel(-1)  # silence Vosk's verbose logging

MODEL_PATH = "./vosk-fa/vosk-model-fa-0.42"   # 0.42 is more accurate than 0.5
AUDIO_IN = "./1.mp3"
SAMPLE_RATE = 16000

# --- 1. Model load (one-time cost) ---
t0 = time.perf_counter()
model = Model(MODEL_PATH)
load_time = time.perf_counter() - t0
print(f"[load]       Model loaded in {load_time:6.2f}s")

rec = KaldiRecognizer(model, SAMPLE_RATE)
rec.SetWords(True)

# --- 2. Transcription (decode + recognize) ---
proc = subprocess.Popen(
    ["ffmpeg", "-loglevel", "quiet", "-i", AUDIO_IN,
     "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "-"],
    stdout=subprocess.PIPE,
)

results = []
total_bytes = 0
recog_time = 0.0           # time spent inside Vosk only
t_start = time.perf_counter()

while True:
    data = proc.stdout.read(4000)
    if len(data) == 0:
        break
    total_bytes += len(data)
    r0 = time.perf_counter()
    if rec.AcceptWaveform(data):
        results.append(json.loads(rec.Result()))
    recog_time += time.perf_counter() - r0

r0 = time.perf_counter()
results.append(json.loads(rec.FinalResult()))
recog_time += time.perf_counter() - r0

wall_time = time.perf_counter() - t_start

# --- 3. Derived metrics ---
# 16kHz mono 16-bit = 2 bytes/sample -> seconds of audio
audio_seconds = total_bytes / (SAMPLE_RATE * 2)
decode_time = wall_time - recog_time   # time spent waiting on ffmpeg I/O

# --- Transcript ---
text = " ".join(r.get("text", "") for r in results if r.get("text"))
print("\n--- TRANSCRIPT ---")
print(text if text else "(empty)")

# --- Timing report ---
print("\n--- TIMING ---")
print(f"Audio length:     {audio_seconds:6.1f}s")
print(f"Model load:       {load_time:6.2f}s")
print(f"Recognition:      {recog_time:6.2f}s  (Vosk compute)")
print(f"Decode/IO:        {decode_time:6.2f}s  (ffmpeg + read)")
print(f"Total transcribe: {wall_time:6.2f}s")
if audio_seconds > 0:
    print(f"Realtime factor:  {wall_time / audio_seconds:6.2f}x  (lower is better; <1 = faster than realtime)")
    print(f"  └ compute only: {recog_time / audio_seconds:6.2f}x")