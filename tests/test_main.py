import os

import numpy as np
import pytest
from types import SimpleNamespace

from swiss_tts import main, config
from swiss_tts.main import SwissTTSEngine


def _make_dummy_downloader():
    """
    Create a mock downloader that always returns fixed model configuration.

    Returns:
        SimpleNamespace: A downloader-like object with a download_and_unpack method
            that returns a dict containing "train_config" and "model_file" keys.
    """
    return SimpleNamespace(
        download_and_unpack=lambda name: {"train_config": "cfg", "model_file": "file"}
    )


class DummyText2Speech:
    def __init__(self, *args, **kwargs):
        self.tts = SimpleNamespace(fs=16000)
        self.use_spembs = False

    def __call__(self, text, **kwargs):
        """
        Return a fixed dictionary with a dummy audio object.

        Returns:
            A dictionary with key 'wav' containing an object whose numpy() method returns [0.1, -0.1].
        """

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
    out = engine.generate_dialect_speech(
        "Hello. World", "testdialect", output_dir=str(tmp_path)
    )

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


# --- Additional tests for changed code in this PR ---


def _make_engine(monkeypatch, text2speech_cls=None):
    """Helper to build a patched SwissTTSEngine."""
    if text2speech_cls is None:
        text2speech_cls = DummyText2Speech
    monkeypatch.setattr(main, "ModelDownloader", _make_dummy_downloader)
    monkeypatch.setattr(main, "Text2Speech", text2speech_cls)
    return SwissTTSEngine()


def test_generate_dialect_speech_raises_on_empty_text(monkeypatch, tmp_path):
    """Empty text string should raise ValueError."""
    monkeypatch.setattr(main, "sf", SimpleNamespace(write=lambda *a, **kw: None))
    engine = _make_engine(monkeypatch)
    with pytest.raises(ValueError, match="text must not be empty"):
        engine.generate_dialect_speech("", "testdialect", output_dir=str(tmp_path))


def test_generate_dialect_speech_raises_on_whitespace_only_text(monkeypatch, tmp_path):
    """Whitespace-only text should raise ValueError."""
    monkeypatch.setattr(main, "sf", SimpleNamespace(write=lambda *a, **kw: None))
    engine = _make_engine(monkeypatch)
    with pytest.raises(ValueError, match="text must not be empty"):
        engine.generate_dialect_speech("   ", "testdialect", output_dir=str(tmp_path))


def test_generate_dialect_speech_raises_on_negative_silence(monkeypatch, tmp_path):
    """Negative silence_duration should raise ValueError."""
    monkeypatch.setattr(main, "sf", SimpleNamespace(write=lambda *a, **kw: None))
    engine = _make_engine(monkeypatch)
    with pytest.raises(ValueError, match="silence_duration must be non-negative"):
        engine.generate_dialect_speech(
            "Hello", "testdialect", silence_duration=-0.1, output_dir=str(tmp_path)
        )


def test_generate_dialect_speech_zero_silence_duration(monkeypatch, tmp_path):
    """silence_duration=0 should be accepted and produce output without silence padding."""
    calls = []

    def fake_write(path, data, samplerate):
        calls.append((path, np.asarray(data), samplerate))

    monkeypatch.setattr(main, "sf", SimpleNamespace(write=fake_write))
    engine = _make_engine(monkeypatch)
    out = engine.generate_dialect_speech(
        "Hello", "testdialect", silence_duration=0.0, output_dir=str(tmp_path)
    )
    assert out.endswith("testdialect_speech.wav")
    assert calls


def test_generate_dialect_speech_output_filename_format(monkeypatch, tmp_path):
    """Output filename should follow the '<dialect_name>_speech.wav' pattern."""
    monkeypatch.setattr(main, "sf", SimpleNamespace(write=lambda *a, **kw: None))
    engine = _make_engine(monkeypatch)
    out = engine.generate_dialect_speech(
        "Hello world", "zurich", output_dir=str(tmp_path)
    )
    assert os.path.basename(out) == "zurich_speech.wav"
    assert str(tmp_path) in out


def test_generate_dialect_speech_punctuation_only_writes_empty_audio(
    monkeypatch, tmp_path
):
    """Text that splits into no valid sentences (punctuation only) should write empty audio."""
    calls = []

    def fake_write(path, data, samplerate):
        calls.append((path, np.asarray(data), samplerate))

    monkeypatch.setattr(main, "sf", SimpleNamespace(write=fake_write))
    engine = _make_engine(monkeypatch)
    out = engine.generate_dialect_speech(
        "... !!! ???", "testdialect", output_dir=str(tmp_path)
    )
    assert out.endswith("testdialect_speech.wav")
    assert calls
    # The written data should be an empty array (or nearly so)
    assert len(calls[0][1]) == 0


def test_generate_dialect_speech_regex_splits_on_exclamation_and_question(
    monkeypatch, tmp_path
):
    """Regex r\"[.!?\\n]\" should split on '!', '?', and newlines in addition to '.'."""
    calls = []

    def fake_write(path, data, samplerate):
        calls.append((path, np.asarray(data), samplerate))

    # Count how many times the TTS is called to verify sentence count
    tts_call_count = []

    class CountingText2Speech(DummyText2Speech):
        def __call__(self, text, **kwargs):
            tts_call_count.append(text)
            return super().__call__(text, **kwargs)

    monkeypatch.setattr(main, "sf", SimpleNamespace(write=fake_write))
    monkeypatch.setattr(main, "ModelDownloader", _make_dummy_downloader)
    monkeypatch.setattr(main, "Text2Speech", CountingText2Speech)

    engine = SwissTTSEngine()
    engine.generate_dialect_speech(
        "Hello! World? Good\nDay.", "testdialect", output_dir=str(tmp_path)
    )
    # "Hello", "World", "Good", "Day" are 4 sentences
    assert len(tts_call_count) == 4


def test_generate_dialect_speech_sample_rate_passed_to_soundfile(
    monkeypatch, tmp_path
):
    """soundfile.write should receive the engine's sample_rate."""
    calls = []

    def fake_write(path, data, samplerate):
        calls.append(samplerate)

    monkeypatch.setattr(main, "sf", SimpleNamespace(write=fake_write))
    engine = _make_engine(monkeypatch)
    engine.generate_dialect_speech("Hello world", "testdialect", output_dir=str(tmp_path))
    assert calls[0] == 16000  # DummyText2Speech sets fs=16000


def test_engine_sets_spembs_from_spk_embed_dim(monkeypatch):
    """When use_spembs=True and tts has spk_embed_dim, kwargs['spembs'] should be set."""
    import torch

    class SpembsText2Speech:
        def __init__(self, *args, **kwargs):
            self.tts = SimpleNamespace(fs=16000, spk_embed_dim=64)
            self.use_spembs = True

        def __call__(self, text, **kwargs):
            class Wav:
                def numpy(self):
                    return np.array([0.0], dtype=np.float32)

            return {"wav": Wav()}

    monkeypatch.setattr(main, "ModelDownloader", _make_dummy_downloader)
    monkeypatch.setattr(main, "Text2Speech", SpembsText2Speech)

    engine = SwissTTSEngine()
    assert "spembs" in engine.kwargs
    assert engine.kwargs["spembs"].shape == (64,)


def test_engine_sets_spembs_from_model_config_fallback(monkeypatch):
    """When use_spembs=True but tts lacks spk_embed_dim, fall back to model_config['spembs']."""
    import torch

    dummy_spembs = torch.zeros(32)

    def download_with_spembs(name):
        return {"train_config": "cfg", "model_file": "file", "spembs": dummy_spembs}

    class SpembsText2SpeechNoAttr:
        def __init__(self, *args, **kwargs):
            self.tts = SimpleNamespace(fs=16000)  # no spk_embed_dim
            self.use_spembs = True

        def __call__(self, text, **kwargs):
            class Wav:
                def numpy(self):
                    return np.array([0.0], dtype=np.float32)

            return {"wav": Wav()}

    monkeypatch.setattr(
        main,
        "ModelDownloader",
        lambda: SimpleNamespace(download_and_unpack=download_with_spembs),
    )
    monkeypatch.setattr(main, "Text2Speech", SpembsText2SpeechNoAttr)

    engine = SwissTTSEngine()
    assert "spembs" in engine.kwargs
    assert engine.kwargs["spembs"] is dummy_spembs


def test_run_uses_default_silence_duration_for_batch(monkeypatch):
    """run() batch loop should use default silence duration (no explicit silence_duration arg)."""
    silence_durations = []
    real_generate = SwissTTSEngine.generate_dialect_speech

    def recording_generate(self, text, dialect_name, silence_duration=config.DEFAULT_SILENCE_DURATION, output_dir="audio_output"):
        silence_durations.append(silence_duration)
        # Don't actually write files
        return os.path.join(output_dir, f"{dialect_name}_speech.wav")

    monkeypatch.setattr(main, "ModelDownloader", _make_dummy_downloader)
    monkeypatch.setattr(main, "Text2Speech", DummyText2Speech)
    monkeypatch.setattr(SwissTTSEngine, "generate_dialect_speech", recording_generate)

    main.run()

    # First call is custom zurich with explicit silence_duration=0.3
    assert silence_durations[0] == 0.3
    # Subsequent calls (batch) pass no silence_duration (None via our wrapper)
    for dur in silence_durations[1:]:
        assert dur is None
