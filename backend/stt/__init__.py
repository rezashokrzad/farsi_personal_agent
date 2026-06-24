import os
from pathlib import Path

from stt.base import SpeechToText
from stt.vosk_backend import VoskSTT, WhisperSTT

_BACKENDS: dict[str, type[SpeechToText]] = {
    "whisper": WhisperSTT,
    "vosk": VoskSTT,
}

WHISPER_MODELS = ("tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "turbo")

_DEFAULT_VOSK_PATH = Path.home() / "Desktop" / "vosk-fa" / "vosk-model-fa-0.42"


def resolve_stt_config() -> tuple[str, str]:
    """Return (backend_id, model_path_or_name) from environment."""
    backend_id = os.getenv("STT_BACKEND", "vosk").lower()
    if backend_id == "vosk":
        model = os.getenv(
            "STT_MODEL",
            os.getenv("VOSK_MODEL_PATH", str(_DEFAULT_VOSK_PATH)),
        )
    else:
        model = os.getenv("STT_MODEL", os.getenv("WHISPER_MODEL", "large"))
    return backend_id, model


def get_stt_backend() -> SpeechToText:
    """
    Create the active STT backend from environment variables.

    STT_BACKEND   — whisper | vosk (default: vosk)
    STT_MODEL     — whisper size name, or vosk model directory path
    VOSK_MODEL_PATH — alias for vosk model path
    WHISPER_MODEL — legacy alias for whisper size
    """
    backend_id, model = resolve_stt_config()

    factory = _BACKENDS.get(backend_id)
    if factory is None:
        options = ", ".join(sorted(_BACKENDS))
        raise ValueError(f"Unknown STT_BACKEND '{backend_id}'. Options: {options}")

    return factory(model)
