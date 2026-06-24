import json
import subprocess
import time
from pathlib import Path

import whisper
from vosk import KaldiRecognizer, Model, SetLogLevel

from stt.base import STTResult, SpeechToText

SetLogLevel(-1)

SAMPLE_RATE = 16000


class WhisperSTT(SpeechToText):
    """OpenAI Whisper local model."""

    def __init__(self, model_name: str):
        self._model_name = model_name
        print(f"Loading Whisper STT model ({model_name})...")
        t0 = time.perf_counter()
        self._model = whisper.load_model(model_name)
        self._load_ms = (time.perf_counter() - t0) * 1000
        print(f"Whisper STT model loaded in {self._load_ms / 1000:.2f}s")

    @property
    def name(self) -> str:
        return f"whisper-{self._model_name}"

    def transcribe(self, audio_path: str, language: str = "fa") -> STTResult:
        t0 = time.perf_counter()
        result = self._model.transcribe(audio_path, language=language, fp16=False)
        duration_ms = (time.perf_counter() - t0) * 1000
        return STTResult(
            text=result["text"].strip(),
            duration_ms=duration_ms,
            compute_ms=duration_ms,
        )


class VoskSTT(SpeechToText):
    """Vosk Farsi model via ffmpeg PCM stream."""

    def __init__(self, model_path: str):
        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(f"Vosk model not found: {path}")
        self._model_path = path
        self._model_id = path.name
        print(f"Loading Vosk STT model ({path})...")
        t0 = time.perf_counter()
        self._model = Model(str(path))
        self._load_ms = (time.perf_counter() - t0) * 1000
        print(f"Vosk STT model loaded in {self._load_ms / 1000:.2f}s")

    @property
    def name(self) -> str:
        return self._model_id

    def transcribe(self, audio_path: str, language: str = "fa") -> STTResult:
        del language  # Vosk fa model is fixed-language
        rec = KaldiRecognizer(self._model, SAMPLE_RATE)
        rec.SetWords(True)

        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-loglevel",
                "quiet",
                "-i",
                audio_path,
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "1",
                "-f",
                "s16le",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        results: list[dict] = []
        total_bytes = 0
        compute_ms = 0.0
        t0 = time.perf_counter()

        assert proc.stdout is not None
        while True:
            data = proc.stdout.read(4000)
            if not data:
                break
            total_bytes += len(data)
            r0 = time.perf_counter()
            if rec.AcceptWaveform(data):
                results.append(json.loads(rec.Result()))
            compute_ms += (time.perf_counter() - r0) * 1000

        r0 = time.perf_counter()
        results.append(json.loads(rec.FinalResult()))
        compute_ms += (time.perf_counter() - r0) * 1000

        proc.wait()
        if proc.returncode != 0:
            err = proc.stderr.read().decode() if proc.stderr else ""
            raise RuntimeError(f"ffmpeg failed (code {proc.returncode}): {err}")

        wall_ms = (time.perf_counter() - t0) * 1000
        decode_ms = max(wall_ms - compute_ms, 0.0)
        audio_seconds = total_bytes / (SAMPLE_RATE * 2)
        text = " ".join(r.get("text", "") for r in results if r.get("text")).strip()

        return STTResult(
            text=text,
            duration_ms=wall_ms,
            audio_seconds=audio_seconds,
            compute_ms=compute_ms,
            decode_ms=decode_ms,
        )
