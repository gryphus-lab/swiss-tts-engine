import pytest
from types import SimpleNamespace

from swiss_tts import translator
from swiss_tts.translator import DialectTranslator


class DummyOpenAI:
    def __init__(self, base_url, api_key, timeout):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.request = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model, messages, temperature):
        self.request = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="  üsbersetztä Text  "))
            ]
        )


def test_translate_to_dialect_uses_local_ollama_and_strips_response(monkeypatch):
    dummy_client = DummyOpenAI("http://localhost:11434/v1", "ollama", 30)
    monkeypatch.setattr(
        translator, "OpenAI", lambda base_url, api_key, timeout: dummy_client
    )

    translator_instance = DialectTranslator()
    translated = translator_instance.translate_to_dialect("Guten Tag", "bern")

    assert translated == "üsbersetztä Text"
    assert translator_instance.client.base_url == "http://localhost:11434/v1"
    assert translator_instance.client.api_key == "ollama"

    request = dummy_client.request
    assert request["model"] == "gemma4"
    assert request["temperature"] == 0.3

    prompt = request["messages"][0]["content"]
    assert "Translate the following standard High German" in prompt
    assert "bern" in prompt
    assert "Guten Tag" in prompt
    assert "Output ONLY the translated text" in prompt


def test_translate_to_dialect_preserves_target_dialect_in_prompt(monkeypatch):
    dummy_client = DummyOpenAI("http://localhost:11434/v1", "ollama", 30)
    monkeypatch.setattr(
        translator, "OpenAI", lambda base_url, api_key, timeout: dummy_client
    )

    translator_instance = DialectTranslator()
    translator_instance.translate_to_dialect("Hallo Welt", "zurich")

    prompt = dummy_client.request["messages"][0]["content"]
    assert "'zurich'" in prompt
    assert "Hallo Welt" in prompt


def test_translate_to_dialect_raises_on_empty_choices(monkeypatch):
    dummy_client = DummyOpenAI("http://localhost:11434/v1", "ollama", 30)
    dummy_client.request = None
    monkeypatch.setattr(
        translator,
        "OpenAI",
        lambda base_url, api_key, timeout=None: dummy_client,
    )

    class EmptyChoicesResponse:
        choices = []

    def create_empty_choices(*args, **kwargs):
        return EmptyChoicesResponse()

    dummy_client.chat.completions.create = create_empty_choices

    translator_instance = DialectTranslator()
    with pytest.raises(ValueError, match="API returned empty choices"):
        translator_instance.translate_to_dialect("Guten Tag", "bern")


def test_translate_to_dialect_rethrows_api_errors(monkeypatch):
    class ErrorOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, *args, **kwargs):
            raise RuntimeError("api failure")

    monkeypatch.setattr(
        translator,
        "OpenAI",
        lambda base_url, api_key, timeout=None: ErrorOpenAI(),
    )

    translator_instance = DialectTranslator()
    with pytest.raises(RuntimeError, match="api failure"):
        translator_instance.translate_to_dialect("Guten Tag", "bern")


def test_dialect_translator_uses_ollama_url_from_env(monkeypatch):
    """When OLLAMA_URL is set, DialectTranslator should pass it as the OpenAI base_url."""
    captured = {}

    def fake_openai(base_url, api_key, timeout):
        captured["base_url"] = base_url
        return DummyOpenAI(base_url, api_key, timeout)

    monkeypatch.setenv("OLLAMA_URL", "http://custom-host:12345/v1")
    monkeypatch.setattr(translator, "OpenAI", fake_openai)

    t = DialectTranslator()
    assert t.client.base_url == "http://custom-host:12345/v1"
    assert captured["base_url"] == "http://custom-host:12345/v1"


def test_dialect_translator_uses_default_url_when_env_absent(monkeypatch):
    """When OLLAMA_URL is not set, DialectTranslator falls back to http://localhost:11434/v1."""
    captured = {}

    def fake_openai(base_url, api_key, timeout):
        captured["base_url"] = base_url
        return DummyOpenAI(base_url, api_key, timeout)

    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.setattr(translator, "OpenAI", fake_openai)

    t = DialectTranslator()
    assert t.client.base_url == "http://localhost:11434/v1"
    assert captured["base_url"] == "http://localhost:11434/v1"


def test_dialect_translator_ollama_url_propagates_to_translation(monkeypatch):
    """OLLAMA_URL env var is used for the actual API request (not just stored)."""
    custom_url = "http://remote-ollama:9999/v1"
    dummy_client = DummyOpenAI(custom_url, "ollama", 30)
    monkeypatch.setenv("OLLAMA_URL", custom_url)
    monkeypatch.setattr(
        translator, "OpenAI", lambda base_url, api_key, timeout: dummy_client
    )

    t = DialectTranslator()
    result = t.translate_to_dialect("Guten Morgen", "zurich")

    assert result == "üsbersetztä Text"
    assert dummy_client.request is not None
    assert dummy_client.request["model"] == "gemma4"
