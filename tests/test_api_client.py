import os

from fastapi.testclient import TestClient

from swiss_tts import api


class DummyTranslator:
    def translate_to_dialect(self, text, dialect):
        return "translated text"


class DummyEngine:
    def generate_dialect_speech(self, text, dialect_name):
        os.makedirs("audio_output", exist_ok=True)
        path = os.path.join("audio_output", f"{dialect_name}_speech.wav")
        with open(path, "wb") as f:
            f.write(b"RIFF")
        return path


def test_fastapi_health_and_synthesize(monkeypatch):
    # Populate models synchronously and disable the background loader to avoid races
    api.models["engine"] = DummyEngine()
    api.models["translator"] = DummyTranslator()
    monkeypatch.setattr(api, "_load_models_background", lambda: None)

    client = TestClient(api.app)

    # Health should report ready because we pre-populated models
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

    # Synthesize an utterance
    payload = {"text": "Guten Tag", "dialect": "zurich", "translate": True}
    r = client.post("/api/v1/synthesize", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["dialect"] == "zurich"
    assert body["translated_text"] == "translated text"

    # The audio_url should point to a file we can fetch
    audio_url = body["audio_url"]
    r2 = client.get(audio_url)
    assert r2.status_code == 200
    assert r2.content.startswith(b"RIFF")


def test_get_audio_file_404(monkeypatch):
    # Ensure no such file exists
    target = os.path.join("audio_output", "definitely_not_present.wav")
    if os.path.exists(target):
        os.remove(target)
    # Disable background loader to avoid launching heavy thread during startup
    monkeypatch.setattr(api, "_load_models_background", lambda: None)
    client = TestClient(api.app)
    r = client.get("/api/v1/audio/definitely_not_present.wav")
    assert r.status_code == 404


def _make_client(monkeypatch, engine=None, translator=None, clear=False):
    """Helper: set up models and return a TestClient with background loader disabled."""
    if clear:
        api.models.clear()
    if engine is not None:
        api.models["engine"] = engine
    if translator is not None:
        api.models["translator"] = translator
    monkeypatch.setattr(api, "_load_models_background", lambda: None)
    return TestClient(api.app)


def test_health_loading_state_via_client(monkeypatch):
    """GET /health returns status='loading' when models dict is empty."""
    api.models.clear()
    client = _make_client(monkeypatch, clear=False)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "loading"


def test_health_error_state_via_client(monkeypatch):
    """GET /health returns status='error' when models dict contains an error."""
    api.models.clear()
    api.models["error"] = "GPU died"
    client = _make_client(monkeypatch)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert "GPU died" in body["message"]


def test_synthesize_503_when_models_have_error(monkeypatch):
    """POST /api/v1/synthesize returns 503 when models dict contains 'error'."""
    api.models.clear()
    api.models["error"] = "init failed"
    client = _make_client(monkeypatch)
    r = client.post("/api/v1/synthesize", json={"text": "Hi", "dialect": "zurich"})
    assert r.status_code == 503
    assert "init failed" in r.json()["detail"]


def test_synthesize_503_when_models_loading(monkeypatch):
    """POST /api/v1/synthesize returns 503 while models are still loading."""
    api.models.clear()
    client = _make_client(monkeypatch)
    r = client.post("/api/v1/synthesize", json={"text": "Hi", "dialect": "zurich"})
    assert r.status_code == 503
    assert "loading" in r.json()["detail"].lower()


def test_synthesize_400_for_invalid_dialect(monkeypatch):
    """POST /api/v1/synthesize returns 400 for an unsupported dialect."""
    client = _make_client(monkeypatch, engine=DummyEngine(), translator=DummyTranslator())
    r = client.post(
        "/api/v1/synthesize",
        json={"text": "Hallo", "dialect": "martian", "translate": False},
    )
    assert r.status_code == 400
    assert "Unsupported dialect" in r.json()["detail"]


def test_synthesize_no_translate_uses_raw_text(monkeypatch):
    """POST /api/v1/synthesize with translate=False passes raw text to the engine."""
    generated_texts = []

    class TrackingEngine:
        def generate_dialect_speech(self, text, dialect_name):
            generated_texts.append(text)
            os.makedirs("audio_output", exist_ok=True)
            path = os.path.join("audio_output", f"{dialect_name}_raw.wav")
            with open(path, "wb") as f:
                f.write(b"RIFF")
            return path

    client = _make_client(
        monkeypatch, engine=TrackingEngine(), translator=DummyTranslator()
    )
    r = client.post(
        "/api/v1/synthesize",
        json={"text": "Original text", "dialect": "zurich", "translate": False},
    )
    assert r.status_code == 200
    assert generated_texts == ["Original text"]
    assert r.json()["translated_text"] == "Original text"


def test_synthesize_500_when_engine_raises(monkeypatch):
    """POST /api/v1/synthesize returns 500 when the TTS engine raises an exception."""

    class FailingEngine:
        def generate_dialect_speech(self, text, dialect_name):
            raise RuntimeError("synthesis crash")

    client = _make_client(
        monkeypatch, engine=FailingEngine(), translator=DummyTranslator()
    )
    r = client.post(
        "/api/v1/synthesize",
        json={"text": "Test", "dialect": "zurich", "translate": False},
    )
    assert r.status_code == 500
    assert "synthesis crash" in r.json()["detail"]


def test_synthesize_bern_dialect(monkeypatch):
    """POST /api/v1/synthesize works for the 'bern' dialect."""
    client = _make_client(monkeypatch, engine=DummyEngine(), translator=DummyTranslator())
    r = client.post(
        "/api/v1/synthesize",
        json={"text": "Guete Tag", "dialect": "bern", "translate": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dialect"] == "bern"
    assert body["status"] == "success"


def test_synthesize_audio_url_format(monkeypatch):
    """The audio_url in the synthesis response follows the /api/v1/audio/{filename} pattern."""
    client = _make_client(monkeypatch, engine=DummyEngine(), translator=DummyTranslator())
    r = client.post(
        "/api/v1/synthesize",
        json={"text": "Hallo", "dialect": "zurich", "translate": False},
    )
    assert r.status_code == 200
    audio_url = r.json()["audio_url"]
    assert audio_url.startswith("/api/v1/audio/")
    assert audio_url.endswith(".wav")
