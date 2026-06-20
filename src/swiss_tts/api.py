# src/swiss_tts/api.py
import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from swiss_tts.main import SwissTTSEngine
from swiss_tts.translator import DialectTranslator
from swiss_tts import config

# Global state for our models so they persist across requests
models = {}


def _load_models_background():
    """Load models in a background thread so the API starts immediately."""
    try:
        print("🔄 Loading models in background...")
        models["engine"] = SwissTTSEngine()
        models["translator"] = DialectTranslator()
        print("✅ Models loaded successfully! Ready for requests.")
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        models["error"] = str(e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start model loading in background thread
    print("🚀 Starting up API server...")
    os.makedirs("audio_output", exist_ok=True)
    thread = threading.Thread(target=_load_models_background, daemon=True)
    thread.start()
    yield
    # Clean up on shutdown
    models.clear()


app = FastAPI(
    title="Swiss TTS Engine API",
    description="REST API for translating and synthesizing Swiss German audio.",
    lifespan=lifespan,
)


# Define the expected JSON payload format
class TTSRequest(BaseModel):
    text: str
    dialect: str = "zurich"
    translate: bool = True  # Set to True if input is Hochdeutsch


@app.get("/health")
def health_check():
    """Check if API is running and if models are loaded."""
    if "error" in models:
        raise HTTPException(status_code=503, detail=models["error"])
    if "engine" not in models or "translator" not in models:
        raise HTTPException(status_code=503, detail="Models still loading...")
    return {"status": "ready", "message": "All models loaded and ready."}


@app.post("/api/v1/synthesize")
def synthesize_speech(request: TTSRequest):
    """Generates audio from text and returns a URL to download the file."""
    # Check if models are ready
    if "error" in models:
        raise HTTPException(
            status_code=503, detail=f"Model loading error: {models['error']}"
        )
    if "engine" not in models or "translator" not in models:
        raise HTTPException(
            status_code=503, detail="Models still loading. Try again in a few moments."
        )

    if request.dialect not in config.SUPPORTED_DIALECTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported dialect. Choose from {config.SUPPORTED_DIALECTS}",
        )

    # 1. Translate if requested
    final_text = request.text
    if request.translate:
        final_text = models["translator"].translate_to_dialect(
            request.text, request.dialect
        )

    # 2. Synthesize audio
    try:
        output_path = models["engine"].generate_dialect_speech(
            text=final_text, dialect_name=request.dialect
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Audio generation failed: {str(e)}"
        )

    filename = os.path.basename(output_path)

    # Return the text actually spoken, and the URL to download the .wav
    return {
        "status": "success",
        "dialect": request.dialect,
        "translated_text": final_text,
        "audio_url": f"/api/v1/audio/{filename}",
    }


@app.get("/api/v1/audio/{filename}")
def get_audio_file(filename: str):
    """Endpoint to fetch the generated .wav file."""
    # Prevent path traversal by stripping directory components
    safe_filename = os.path.basename(filename)
    file_path = os.path.join("audio_output", safe_filename)

    # Verify the resolved path stays within audio_output directory
    audio_dir = os.path.abspath("audio_output")
    resolved_path = os.path.abspath(file_path)
    if not resolved_path.startswith(audio_dir + os.sep):
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail="Audio file not found on server.")

    return FileResponse(resolved_path, media_type="audio/wav", filename=safe_filename)
