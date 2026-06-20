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
    (repo_root / "texts.json").write_text(
        json.dumps({"basel": "Sali"}), encoding="utf8"
    )

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


# --- Additional tests for changed code in this PR ---


def test_default_fallback_texts_contains_all_dialects():
    """Verify DEFAULT_FALLBACK_TEXTS has all three dialect keys (basel entry had trailing comma added)."""
    assert set(config.DEFAULT_FALLBACK_TEXTS.keys()) == {"zurich", "bern", "basel"}


def test_default_fallback_texts_basel_is_string():
    """The 'basel' entry (which had trailing comma added) should be a non-empty string."""
    value = config.DEFAULT_FALLBACK_TEXTS["basel"]
    assert isinstance(value, str) and value.strip()


def test_default_fallback_texts_all_values_non_empty():
    """All fallback text values should be non-empty strings."""
    for dialect, text in config.DEFAULT_FALLBACK_TEXTS.items():
        assert isinstance(text, str) and text.strip(), (
            f"Dialect '{dialect}' has empty or non-string fallback text"
        )


def test_normalize_text_value_empty_list():
    """An empty list should return None."""
    assert config._normalize_text_value([]) is None


def test_normalize_text_value_list_with_only_empty_strings():
    """A list containing only empty/whitespace strings should return None."""
    assert config._normalize_text_value(["", "   ", ""]) is None


def test_normalize_text_value_list_with_mixed_empty_and_valid():
    """Empty strings in a list should be skipped; valid strings joined."""
    assert config._normalize_text_value(["", "hello", "   ", "world"]) == "hello world"


def test_normalize_text_value_non_string_non_list():
    """A non-string, non-list value (e.g. integer) should return None."""
    assert config._normalize_text_value(42) is None


def test_normalize_text_value_none_input():
    """None input should return None."""
    assert config._normalize_text_value(None) is None


def test_normalize_text_value_whitespace_only_string():
    """A string containing only whitespace should return None."""
    assert config._normalize_text_value("   ") is None


def test_normalize_texts_empty_dict_returns_none():
    """An empty dict (no valid str/list values) should return None."""
    assert config._normalize_texts({}) is None


def test_normalize_texts_skips_non_string_non_list_values():
    """Keys whose values are not str or list should be excluded from result."""
    raw = {"zurich": "Grüezi", "count": 5, "nested": {"a": "b"}}
    result = config._normalize_texts(raw)
    assert result == {"zurich": "Grüezi"}


def test_normalize_texts_returns_none_if_all_values_invalid():
    """A dict with only non-str/non-list values should return None."""
    raw = {"a": 1, "b": None, "c": 3.14}
    assert config._normalize_texts(raw) is None


def test_normalize_texts_with_list_input():
    """Passing a list (not a dict) should return None."""
    assert config._normalize_texts(["zurich", "bern"]) is None


def test_read_json_file_returns_parsed_object(tmp_path):
    """Valid JSON file should be parsed and returned."""
    json_file = tmp_path / "texts.json"
    json_file.write_text(json.dumps({"zurich": "Grüezi"}), encoding="utf8")
    result = config._read_json_file(json_file)
    assert result == {"zurich": "Grüezi"}


def test_load_texts_from_json_returns_none_when_no_candidates(tmp_path, monkeypatch):
    """When neither candidate file exists, should return None."""
    empty_root = tmp_path / "empty_repo"
    empty_root.mkdir()

    class DummyPath:
        def __init__(self, *args):
            pass

        def resolve(self):
            class Resolved:
                parents = [None, None, empty_root]

            return Resolved()

    monkeypatch.setattr(config, "Path", DummyPath)
    assert config._load_texts_from_json() is None


def test_load_texts_from_json_falls_back_to_config_dir(tmp_path, monkeypatch):
    """When root texts.json is absent but config/texts.json exists, use the config dir."""
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "config" / "texts.json").write_text(
        json.dumps({"zurich": "Grüezi"}), encoding="utf8"
    )
    # No root-level texts.json created

    class DummyPath:
        def __init__(self, *args):
            pass

        def resolve(self):
            class Resolved:
                parents = [None, None, repo_root]

            return Resolved()

    monkeypatch.setattr(config, "Path", DummyPath)
    assert config._load_texts_from_json() == {"zurich": "Grüezi"}


def test_load_texts_from_json_skips_invalid_json_and_falls_back(tmp_path, monkeypatch):
    """Invalid root JSON should be skipped, falling back to config/texts.json."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "texts.json").write_text("{ invalid json", encoding="utf8")
    (repo_root / "config").mkdir()
    (repo_root / "config" / "texts.json").write_text(
        json.dumps({"bern": "Grüessech"}), encoding="utf8"
    )

    class DummyPath:
        def __init__(self, *args):
            pass

        def resolve(self):
            class Resolved:
                parents = [None, None, repo_root]

            return Resolved()

    monkeypatch.setattr(config, "Path", DummyPath)
    assert config._load_texts_from_json() == {"bern": "Grüessech"}
