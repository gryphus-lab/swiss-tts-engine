import os
from types import SimpleNamespace

import pytest

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
    resp = api.health_check()
    assert resp["status"] == "loading"


def test_health_check_error_propagates():
    api.models["error"] = "boom"
    resp = api.health_check()
    assert resp["status"] == "error"
    assert "boom" in resp["message"]


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


def test_health_check_ready_when_both_models_present():
    """health_check returns 'ready' only when both engine and translator are loaded."""
    api.models["engine"] = SimpleNamespace()
    api.models["translator"] = SimpleNamespace()
    resp = api.health_check()
    assert resp["status"] == "ready"
    assert "ready" in resp["message"].lower()


def test_health_check_loading_when_only_engine_present():
    """health_check returns 'loading' if translator is absent."""
    api.models["engine"] = SimpleNamespace()
    resp = api.health_check()
    assert resp["status"] == "loading"


def test_health_check_loading_when_only_translator_present():
    """health_check returns 'loading' if engine is absent."""
    api.models["translator"] = SimpleNamespace()
    resp = api.health_check()
    assert resp["status"] == "loading"


def test_synthesize_raises_503_when_models_have_error():
    """synthesize_speech raises HTTPException(503) when models dict contains 'error'."""
    api.models["error"] = "VRAM OOM"
    req = api.TTSRequest(text="Test", dialect="zurich", translate=False)
    with pytest.raises(Exception) as exc:
        api.synthesize_speech(req)
    assert "503" in str(exc.value) or "VRAM OOM" in str(exc.value)


def test_synthesize_raises_503_when_models_still_loading():
    """synthesize_speech raises HTTPException(503) when models are not yet loaded."""
    # models dict is empty (cleared by fixture)
    req = api.TTSRequest(text="Test", dialect="zurich", translate=False)
    with pytest.raises(Exception) as exc:
        api.synthesize_speech(req)
    assert "503" in str(exc.value) or "loading" in str(exc.value).lower()


def test_synthesize_no_translation_when_translate_false(monkeypatch, tmp_path):
    """When translate=False, the translator is NOT called and original text is used."""
    translate_calls = []

    class TrackingTranslator:
        def translate_to_dialect(self, text, dialect):
            translate_calls.append((text, dialect))
            return "should not be returned"

    class DummyEngine:
        def generate_dialect_speech(self, text, dialect_name):
            return str(tmp_path / f"{dialect_name}.wav")

    monkeypatch.setattr(
        api,
        "models",
        {"engine": DummyEngine(), "translator": TrackingTranslator()},
    )

    req = api.TTSRequest(text="Grüezi Wohl", dialect="zurich", translate=False)
    resp = api.synthesize_speech(req)

    assert translate_calls == [], "translator must not be called when translate=False"
    assert resp["translated_text"] == "Grüezi Wohl"


def test_synthesize_raises_500_when_engine_raises(monkeypatch):
    """synthesize_speech raises HTTPException(500) when the TTS engine throws."""

    class BrokenEngine:
        def generate_dialect_speech(self, text, dialect_name):
            raise RuntimeError("GPU exploded")

    monkeypatch.setattr(
        api,
        "models",
        {"engine": BrokenEngine(), "translator": SimpleNamespace()},
    )

    req = api.TTSRequest(text="Test", dialect="zurich", translate=False)
    with pytest.raises(Exception) as exc:
        api.synthesize_speech(req)
    assert "500" in str(exc.value) or "GPU exploded" in str(exc.value)


def test_tts_request_default_dialect_and_translate():
    """TTSRequest defaults: dialect='zurich', translate=True."""
    req = api.TTSRequest(text="anything")
    assert req.dialect == "zurich"
    assert req.translate is True


def test_tts_request_custom_values():
    """TTSRequest accepts explicit dialect and translate=False."""
    req = api.TTSRequest(text="Guete Morge", dialect="bern", translate=False)
    assert req.dialect == "bern"
    assert req.translate is False


def test_load_models_background_success(monkeypatch):
    """_load_models_background populates engine and translator on success."""
    api.models.clear()

    class FakeEngine:
        pass

    class FakeTranslator:
        pass

    monkeypatch.setattr(api, "SwissTTSEngine", FakeEngine)
    monkeypatch.setattr(api, "DialectTranslator", FakeTranslator)

    api._load_models_background()

    assert "engine" in api.models
    assert isinstance(api.models["engine"], FakeEngine)
    assert "translator" in api.models
    assert isinstance(api.models["translator"], FakeTranslator)
    assert "error" not in api.models


def test_load_models_background_on_exception(monkeypatch):
    """_load_models_background sets models['error'] when instantiation fails."""
    api.models.clear()

    def broken_engine():
        raise RuntimeError("out of memory")

    monkeypatch.setattr(api, "SwissTTSEngine", broken_engine)

    api._load_models_background()

    assert "error" in api.models
    assert "out of memory" in api.models["error"]
    assert "engine" not in api.models


def test_get_audio_file_media_type(tmp_path):
    """get_audio_file returns a FileResponse with audio/wav media type."""
    os.makedirs("audio_output", exist_ok=True)
    fname = "media_type_test.wav"
    path = os.path.join("audio_output", fname)
    with open(path, "wb") as f:
        f.write(b"RIFF")

    resp = api.get_audio_file(fname)
    assert resp.media_type == "audio/wav"


def test_synthesize_all_supported_dialects(monkeypatch, tmp_path):
    """synthesize_speech succeeds for every dialect in SUPPORTED_DIALECTS."""

    class DummyTranslator:
        def translate_to_dialect(self, text, dialect):
            return text

    class DummyEngine:
        def generate_dialect_speech(self, text, dialect_name):
            return str(tmp_path / f"{dialect_name}.wav")

    monkeypatch.setattr(
        api,
        "models",
        {"engine": DummyEngine(), "translator": DummyTranslator()},
    )

    for dialect in config.SUPPORTED_DIALECTS:
        req = api.TTSRequest(text="Hallo", dialect=dialect, translate=False)
        resp = api.synthesize_speech(req)
        assert resp["status"] == "success"
        assert resp["dialect"] == dialect
