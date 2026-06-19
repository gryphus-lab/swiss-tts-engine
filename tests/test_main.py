import numpy as np
from types import SimpleNamespace
import os

from swiss_tts import main, config
from swiss_tts.main import SwissTTSEngine


def _make_dummy_downloader():
    return SimpleNamespace(download_and_unpack=lambda name: {"train_config": "cfg", "model_file": "file"})


class DummyText2Speech:
    def __init__(self, *args, **kwargs):
        self.tts = SimpleNamespace(fs=16000)
        self.use_spembs = False

    def __call__(self, text, **kwargs):
        class Wav:
            def __init__(self):
                self._arr = np.array([0.1, -0.1], dtype=np.float32)

            def numpy(self):
                return self._arr

        return {"wav": Wav()}


def test_generate_dialect_speech_saves_file(tmp_path, monkeypatch):
    calls = []

    def fake_write(path, data, samplerate):
        calls.append((path, np.asarray(data), samplerate))

    # Patch heavy dependencies in the module under test
    monkeypatch.setattr(main, "ModelDownloader", _make_dummy_downloader)
    monkeypatch.setattr(main, "Text2Speech", DummyText2Speech)
    monkeypatch.setattr(main, "sf", SimpleNamespace(write=fake_write))

    engine = SwissTTSEngine()
    out = engine.generate_dialect_speech("Hello. World", "testdialect", output_dir=str(tmp_path))

    assert os.path.exists(str(tmp_path))
    assert out.endswith("testdialect_speech.wav")
    # Ensure soundfile.write was called with correct sample rate
    assert calls and calls[0][2] == 16000


def test_run_writes_for_all_dialects(monkeypatch):
    calls = []

    def fake_write(path, data, samplerate):
        calls.append(path)

    monkeypatch.setattr(main, "ModelDownloader", _make_dummy_downloader)
    monkeypatch.setattr(main, "Text2Speech", DummyText2Speech)
    monkeypatch.setattr(main, "sf", SimpleNamespace(write=fake_write))

    # Run the module-level runner
    main.run()

    # One for the custom_zuri and one per default fallback dialect
    expected = 1 + len(config.DEFAULT_FALLBACK_TEXTS)
    assert len(calls) == expected
