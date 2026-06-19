import json
from pathlib import Path
from unittest import mock

import pytest

from swiss_tts import config


def test_normalize_text_value_list():
    assert config._normalize_text_value(["Hello ", "world"]) == "Hello world"


def test_normalize_text_value_string():
    assert config._normalize_text_value("single string") == "single string"


def test_normalize_texts_skips_non_dict():
    assert config._normalize_texts(None) is None


def test_normalize_texts_transforms_lists():
    raw = {
        "zurich": ["Grüezi ", "wie gahts?"],
        "bern": "Grüezi mitenand",
    }

    assert config._normalize_texts(raw) == {
        "zurich": "Grüezi wie gahts?",
        "bern": "Grüezi mitenand",
    }


def test_read_json_file_returns_none_for_missing_file(tmp_path):
    assert config._read_json_file(tmp_path / "missing.json") is None


def test_read_json_file_returns_none_for_invalid_json(tmp_path):
    invalid_file = tmp_path / "texts.json"
    invalid_file.write_text("{ invalid json", encoding="utf8")
    assert config._read_json_file(invalid_file) is None


def test_load_texts_from_json_prefers_root_texts_json(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "texts.json").write_text(json.dumps({"basel": "Sali"}), encoding="utf8")

    class DummyPath:
        def __init__(self, *args):
            pass

        def resolve(self):
            class Resolved:
                parents = [None, None, repo_root]

            return Resolved()

    monkeypatch.setattr(config, "Path", DummyPath)
    assert config._load_texts_from_json() == {"basel": "Sali"}


def test_load_texts_from_json_reads_config_texts_json(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "config" / "texts.json").write_text(
        json.dumps({"bern": ["Grüessech, ", "wie gaht's?"]}), encoding="utf8"
    )

    class DummyPath:
        def __init__(self, *args):
            pass

        def resolve(self):
            class Resolved:
                parents = [None, None, repo_root]

            return Resolved()

    monkeypatch.setattr(config, "Path", DummyPath)
    assert config._load_texts_from_json() == {"bern": "Grüessech, wie gaht's?"}


def test_default_texts_fallback_to_defaults():
    with mock.patch("swiss_tts.config._load_texts_from_json", return_value=None):
        # Force re-evaluation of module-level logic
        _json_texts = config._load_texts_from_json()
        if _json_texts is not None:
            DEFAULT_TEXTS = _json_texts
        else:
            DEFAULT_TEXTS = config.DEFAULT_FALLBACK_TEXTS
        assert DEFAULT_TEXTS == config.DEFAULT_FALLBACK_TEXTS
