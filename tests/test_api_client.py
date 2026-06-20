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
