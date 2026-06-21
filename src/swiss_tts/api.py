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
    if request.dialect not in config.SUPPORTED_DIALECTS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported dialect. Choose from {config.SUPPORTED_DIALECTS}"
        )

    if "error" in models:
        raise HTTPException(status_code=503, detail=f"Model loading error: {models['error']}")

    if "engine" not in models or "translator" not in models:
        raise HTTPException(status_code=503, detail="Models still loading...")

    # 1. ALWAYS format the text phonetically via the LLM
    final_text = models["translator"].translate_to_dialect(request.text, request.dialect)

    # 2. Synthesize audio
    try:
        output_path = models["engine"].generate_dialect_speech(
            text=final_text,
            dialect_name=request.dialect
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {str(e)}")

    filename = os.path.basename(output_path)
    
    return {
        "status": "success",
        "dialect": request.dialect,
        "translated_text": final_text,
        "audio_url": f"/api/v1/audio/{filename}"
    }


@app.get("/api/v1/audio/{filename}")
def get_audio_file(filename: str):
    """
    Serve a generated audio file from the output directory with path traversal protection.

    Validates that the requested file path remains within the audio_output directory to prevent
    directory traversal attacks.

    Parameters:
        filename (str): The requested audio filename.

    Returns:
        FileResponse: The audio file with audio/wav media type.

    Raises:
        HTTPException: With status 400 if the file path is invalid or outside the audio_output directory;
                with status 404 if the file does not exist.
    """
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


@app.get("/")
def serve_frontend():
    """Serves the simple HTML frontend."""
    frontend_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "public", "index.html"
    )
    resolved_path = os.path.abspath(frontend_path)
    return FileResponse(resolved_path)
