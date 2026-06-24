from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class STTResult:
    text: str
    duration_ms: float
    audio_seconds: float = 0.0
    compute_ms: float = 0.0
    decode_ms: float = 0.0

    def metrics(self) -> dict:
        out = {
            "duration_ms": round(self.duration_ms, 1),
            "audio_seconds": round(self.audio_seconds, 2),
            "compute_ms": round(self.compute_ms, 1),
            "decode_ms": round(self.decode_ms, 1),
        }
        if self.audio_seconds > 0:
            out["realtime_factor"] = round(self.duration_ms / 1000 / self.audio_seconds, 2)
            out["compute_rtf"] = round(self.compute_ms / 1000 / self.audio_seconds, 2)
        return out


class SpeechToText(ABC):
    """Pluggable speech-to-text backend."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier used in logs and health checks."""

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "fa") -> STTResult:
        """Transcribe audio file and return text with timing metrics."""
