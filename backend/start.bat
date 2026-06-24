@echo off
echo Starting Farsi Voice Agent Backend...
echo.
echo Make sure you have:
echo   1. Python 3.10+ installed
echo   2. Ollama running with: ollama serve
echo   3. Qwen3:1.7b pulled with: ollama pull qwen3:1.7b
echo   4. ffmpeg on PATH (required for Vosk STT)
echo   5. STT defaults to Vosk. Switch backends:
echo      set STT_BACKEND=vosk
echo      set STT_MODEL=C:\Users\rezas\Desktop\vosk-fa\vosk-model-fa-0.42
echo      set STT_BACKEND=whisper
echo      set STT_MODEL=medium
echo.
cd /d "%~dp0"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
