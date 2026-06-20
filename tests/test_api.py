import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from swiss_tts import api, config


@pytest.fixture(autouse=True)
def clear_models(monkeypatch):
    # Ensure we start each test with a clean models dict
    monkeypatch.setattr(api, "models", {})
    yield
    api.models.clear()


def test_health_check_loading_when_models_absent():
    api.models.clear()
    with pytest.raises(HTTPException) as exc:
        api.health_check()
    assert exc.value.status_code == 503
    assert "Models still loading" in str(exc.value.detail)


def test_health_check_error_propagates():
    api.models["error"] = "boom"
    with pytest.raises(HTTPException) as exc:
        api.health_check()
    assert exc.value.status_code == 503
    assert exc.value.detail == "boom"


def test_synthesize_raises_for_unsupported_dialect():
    # provide dummy ready models
    api.models["engine"] = SimpleNamespace()
    api.models["translator"] = SimpleNamespace()

    req = api.TTSRequest(text="Hallo", dialect="invalid", translate=False)
    with pytest.raises(Exception) as exc:
        api.synthesize_speech(req)
    assert "Unsupported dialect" in str(exc.value)


def test_synthesize_translates_and_calls_engine(monkeypatch, tmp_path):
    calls = []

    class DummyTranslator:
        def translate_to_dialect(self, text, dialect):
            calls.append(("translate", text, dialect))
            return "translated text"

    class DummyEngine:
        def generate_dialect_speech(self, text, dialect_name):
            calls.append(("generate", text, dialect_name))
            return str(tmp_path / f"{dialect_name}_speech.wav")

    monkeypatch.setattr(api, "models", {"engine": DummyEngine(), "translator": DummyTranslator()})

    req = api.TTSRequest(text="Guten Tag", dialect="zurich", translate=True)
    resp = api.synthesize_speech(req)

    assert resp["status"] == "success"
    assert resp["dialect"] == "zurich"
    assert resp["translated_text"] == "translated text"
    assert resp["audio_url"].endswith("zurich_speech.wav")
    assert ("translate", "Guten Tag", "zurich") in calls
    assert any(c[0] == "generate" for c in calls)


def test_get_audio_file_not_found_raises():
    # ensure file does not exist
    filename = "no_such_file.wav"
    if os.path.exists(os.path.join("audio_output", filename)):
        os.remove(os.path.join("audio_output", filename))

    with pytest.raises(Exception) as exc:
        api.get_audio_file(filename)
    assert "not found" in str(exc.value).lower()


def test_get_audio_file_returns_fileresponse(tmp_path):
    # create audio_output dir and file
    os.makedirs("audio_output", exist_ok=True)
    fname = "testfile.wav"
    path = os.path.join("audio_output", fname)
    with open(path, "wb") as f:
        f.write(b"RIFF")

    resp = api.get_audio_file(fname)
    assert isinstance(resp, FileResponse)
    assert resp.filename == fname
