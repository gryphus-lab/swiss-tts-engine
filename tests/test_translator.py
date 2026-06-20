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
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self.create)
            )

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
