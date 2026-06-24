import io
import json
import os
import re
import tempfile
import time
from datetime import datetime

import edge_tts
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pipeline_log import PipelineReport, setup_pipeline_logging
from stt import WHISPER_MODELS, get_stt_backend, resolve_stt_config
from stt.base import STTResult

app = FastAPI(title="Farsi Voice Agent")
setup_pipeline_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "600"))
STT_BACKEND, STT_MODEL = resolve_stt_config()
TTS_VOICE = "fa-IR-DilaraNeural"
TTS_RATE = "+8%"
TTS_PITCH = "+12Hz"

stt = get_stt_backend()


@app.on_event("startup")
async def warmup_ollama():
    """Keep the LLM loaded so the first user request is not a cold start."""
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            await client.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": "سلام"}],
                    "stream": False,
                    "think": True,
                },
            )
        print("Ollama model warmed up.")
    except Exception as e:
        print(f"Ollama warmup skipped: {e}")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_model": OLLAMA_MODEL,
        "stt_backend": STT_BACKEND,
        "stt_model": STT_MODEL,
        "stt_name": stt.name,
        "whisper_models": list(WHISPER_MODELS),
        "stt_backends": ["vosk", "whisper"],
    }


def _record_stt(
    report: PipelineReport | None,
    audio_input: object,
    result: STTResult,
) -> None:
    if report:
        report.record(
            "stt",
            stt.name,
            result.duration_ms,
            audio_input,
            result.text,
            metrics=result.metrics(),
        )


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Receive audio file, return Farsi transcription."""
    report = PipelineReport("transcribe")
    data = await audio.read()
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = stt.transcribe(tmp_path, language="fa")
        _record_stt(report, data, result)
        text = result.text
    finally:
        os.unlink(tmp_path)

    timing = report.finish()
    return {"text": text, "timing": timing}


_PERSIAN_CHAR = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
_CJK_CHAR = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def _farsi_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = [c for c in text if c.isalpha() or _PERSIAN_CHAR.match(c)]
    if not letters:
        return 0.0
    persian = sum(1 for c in letters if _PERSIAN_CHAR.match(c))
    return persian / len(letters)


def _extract_farsi(text: str) -> str:
    """Pull the last Persian sentence out of mixed-language model output."""
    chunks = re.findall(
        r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF"
        r"\u200c\s،.!؟\-'\"0-9]+",
        text,
    )
    chunks = [c.strip(" ،.!؟\n") for c in chunks if _farsi_ratio(c) >= 0.5]
    return chunks[-1] if chunks else ""


def _clean_llm_response(raw: str) -> str:
    """Keep only the final Persian answer."""
    for tag in ("think", "redacted_thinking"):
        if re.search(rf"</{tag}>", raw, flags=re.IGNORECASE):
            raw = re.split(rf"</{tag}>", raw, flags=re.IGNORECASE)[-1]
        raw = re.sub(rf"<{tag}>.*?</{tag}>", "", raw, flags=re.DOTALL | re.IGNORECASE)

    raw = _CJK_CHAR.sub("", raw).strip()

    if _farsi_ratio(raw) < 0.5:
        farsi = _extract_farsi(raw)
        if farsi:
            raw = farsi

    return raw.strip()


async def _llm_complete(prompt: str, system: str | None = None, report: PipelineReport | None = None, skip_clean: bool = False) -> str:
    """Send prompt to Qwen3 via Ollama, return full response."""
    if system is None:
        system = "تو یک دستیار فارسی هستی. فقط به فارسی پاسخ بده. پاسخ کوتاه و مستقیم باشد."
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": True,
    }
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    msg = data["message"]
    raw = msg.get("content", "")
    cleaned = raw.strip() if skip_clean else _clean_llm_response(raw)
    if not cleaned:
        raise ValueError("model returned an empty response")
    if report:
        report.record("llm", OLLAMA_MODEL, (time.perf_counter() - t0) * 1000, prompt, cleaned)
    return cleaned


async def _tts_bytes(text: str, report: PipelineReport | None = None) -> bytes:
    """Convert text to speech, return MP3 bytes."""
    t0 = time.perf_counter()
    communicate = edge_tts.Communicate(
        text, voice=TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH
    )
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    audio = buf.read()
    if report:
        report.record(
            "tts",
            f"edge-tts:{TTS_VOICE}",
            (time.perf_counter() - t0) * 1000,
            text,
            audio,
        )
    return audio


async def _detect_calendar_intent(user_text: str) -> dict | None:
    """Step 1: dedicated JSON-only prompt to detect calendar intent reliably."""
    today = datetime.now().strftime("%Y-%m-%d")
    system = (
        "You extract calendar actions from Persian text and return ONLY raw JSON, no explanation.\n"
        f"Today is {today}. Timezone offset for Iran is +03:30.\n\n"
        "Rules:\n"
        "- If user wants to CREATE an event, return:\n"
        '  {"action":"create","title":"...","start":"YYYY-MM-DDTHH:MM:SS+03:30","end":"YYYY-MM-DDTHH:MM:SS+03:30","guests":[]}\n'
        "- If user wants to DELETE an event, return:\n"
        '  {"action":"delete","title":"..."}\n'
        "- If user wants to LIST events, return:\n"
        '  {"action":"list"}\n'
        "- If it is NOT a calendar request, return:\n"
        '  {"action":"none"}\n'
        "Return ONLY the JSON object, nothing else."
    )
    try:
        raw = await _llm_complete(user_text, system=system, skip_clean=True)
        m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        if not m:
            return None
        cmd = json.loads(m.group())
        return cmd if cmd.get("action") not in (None, "none") else None
    except Exception:
        return None


async def _execute_calendar(cmd: dict) -> str:
    """Step 2: execute the calendar command, return Persian result string."""
    import asyncio
    from calendar_agent import create_event, delete_event, list_events

    action = cmd.get("action", "")
    try:
        if action == "create":
            return await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: create_event(
                    title=cmd.get("title", "رویداد"),
                    start_iso=cmd["start"],
                    end_iso=cmd.get("end"),
                    guests=cmd.get("guests", []),
                    description=cmd.get("description", ""),
                ),
            )
        elif action == "delete":
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: delete_event(cmd.get("title", ""))
            )
        elif action == "list":
            return await asyncio.get_event_loop().run_in_executor(None, list_events)
    except Exception as e:
        return f"خطا در تقویم: {e}"
    return ""


@app.post("/pipeline")
async def pipeline(audio: UploadFile = File(...)):
    """Full pipeline: audio -> STT -> LLM -> TTS -> audio response."""
    from urllib.parse import quote

    report = PipelineReport("pipeline")
    data = await audio.read()
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        result = stt.transcribe(tmp_path, language="fa")
        user_text = result.text
        _record_stt(report, data, result)
    finally:
        os.unlink(tmp_path)

    if not user_text:
        raise HTTPException(status_code=400, detail="Could not transcribe audio")

    import asyncio as _asyncio
    try:
        intent_task = _asyncio.create_task(_detect_calendar_intent(user_text))
        chat_task = _asyncio.create_task(_llm_complete(user_text, report=report))
        cal_cmd, chat_reply = await _asyncio.gather(intent_task, chat_task, return_exceptions=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

    if isinstance(chat_reply, Exception):
        raise HTTPException(status_code=502, detail=f"LLM error: {chat_reply}")

    if isinstance(cal_cmd, dict):
        cal_result = await _execute_calendar(cal_cmd)
        assistant_text = cal_result if cal_result else chat_reply
    else:
        assistant_text = chat_reply

    try:
        audio_bytes = await _tts_bytes(assistant_text, report)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS error: {e}")

    if not audio_bytes:
        raise HTTPException(status_code=502, detail="TTS produced empty audio")

    timing = report.finish()

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={
            "X-User-Text": quote(user_text),
            "X-Assistant-Text": quote(assistant_text),
            "X-Pipeline-Timing": quote(json.dumps(timing, ensure_ascii=False)),
            "Access-Control-Expose-Headers": "X-User-Text, X-Assistant-Text, X-Pipeline-Timing",
        },
    )


@app.post("/chat-text")
async def chat_text(body: dict):
    """Text-only chat for testing."""
    prompt = body.get("text", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="No text provided")
    report = PipelineReport("chat-text")
    import asyncio as _asyncio
    try:
        cal_cmd, chat_reply = await _asyncio.gather(
            _detect_calendar_intent(prompt),
            _llm_complete(prompt, report=report),
            return_exceptions=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")
    if isinstance(chat_reply, Exception):
        raise HTTPException(status_code=502, detail=f"LLM error: {chat_reply}")
    if isinstance(cal_cmd, dict):
        cal_result = await _execute_calendar(cal_cmd)
        response = cal_result if cal_result else chat_reply
    else:
        response = chat_reply
    timing = report.finish()
    return {"response": response, "timing": timing}
