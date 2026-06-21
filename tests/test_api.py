import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from swiss_tts import api


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

    monkeypatch.setattr(
        api, "models", {"engine": DummyEngine(), "translator": DummyTranslator()}
    )

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


def test_health_check_ready_when_models_present():
    api.models["engine"] = SimpleNamespace()
    api.models["translator"] = SimpleNamespace()

    result = api.health_check()
    assert result == {
        "status": "ready",
        "message": "All models loaded and ready.",
    }


def test_synthesize_raises_for_model_loading_error():
    api.models["error"] = "engine failed"
    req = api.TTSRequest(text="Hallo", dialect="zurich", translate=False)

    with pytest.raises(HTTPException) as exc:
        api.synthesize_speech(req)

    assert exc.value.status_code == 503
    assert "Model loading error" in exc.value.detail


def test_synthesize_raises_when_models_not_ready():
    api.models["engine"] = SimpleNamespace()
    req = api.TTSRequest(text="Hallo", dialect="zurich", translate=False)

    with pytest.raises(HTTPException) as exc:
        api.synthesize_speech(req)

    assert exc.value.status_code == 503
    assert "Models still loading" in exc.value.detail


def test_synthesize_raises_on_engine_exception(monkeypatch):
    class BrokenEngine:
        def generate_dialect_speech(self, text, dialect_name):
            raise RuntimeError("synthesis failed")

    api.models["engine"] = BrokenEngine()
    api.models["translator"] = SimpleNamespace(
        translate_to_dialect=lambda text, dialect: text
    )

    req = api.TTSRequest(text="Hallo", dialect="zurich", translate=True)
    with pytest.raises(HTTPException) as exc:
        api.synthesize_speech(req)

    assert exc.value.status_code == 500
    assert "Audio generation failed" in exc.value.detail


def test_load_models_background_sets_models_success(monkeypatch):
    class DummyEngine:
        pass

    class DummyTranslator:
        pass

    monkeypatch.setattr(api, "SwissTTSEngine", DummyEngine)
    monkeypatch.setattr(api, "DialectTranslator", DummyTranslator)

    api.models.clear()
    api._load_models_background()

    assert isinstance(api.models["engine"], DummyEngine)
    assert isinstance(api.models["translator"], DummyTranslator)


def test_load_models_background_captures_exception(monkeypatch):
    class DummyTranslator:
        pass

    def failing_engine():
        raise RuntimeError("boom")

    monkeypatch.setattr(api, "SwissTTSEngine", failing_engine)
    monkeypatch.setattr(api, "DialectTranslator", DummyTranslator)

    api.models.clear()
    api._load_models_background()

    assert api.models["error"] == "boom"


def test_lifespan_creates_audio_output_and_clears_models(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "_load_models_background", lambda: None)

    import asyncio

    async def run_context():
        async with api.lifespan(api.app):
            assert os.path.isdir(tmp_path / "audio_output")
            assert api.models == {}

    asyncio.run(run_context())
    assert api.models == {}


def test_get_audio_file_rejects_empty_filename():
    with pytest.raises(HTTPException) as exc:
        api.get_audio_file("")

    assert exc.value.status_code == 400
    assert "Invalid file path" in exc.value.detail


def test_serve_frontend_returns_index_html():
    resp = api.serve_frontend()
    assert isinstance(resp, FileResponse)
    assert resp.path.endswith("public/index.html")
