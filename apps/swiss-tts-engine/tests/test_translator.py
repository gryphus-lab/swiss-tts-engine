import subprocess
from types import SimpleNamespace

import pytest
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
    monkeypatch.setattr(
        translator,
        "OpenAI",
        lambda base_url, api_key, timeout: DummyOpenAI(base_url, api_key, timeout),
    )

    translator_instance = DialectTranslator()
    translated = translator_instance.translate_to_dialect("Guten Tag", "bern")

    assert translated == "üsbersetztä Text"
    assert translator_instance.client.base_url == "http://localhost:11434/v1"
    assert translator_instance.client.api_key == "ollama"
    assert translator_instance.client.timeout == 30

    dummy_client = translator_instance.client
    request = dummy_client.request
    assert request["model"] == "gemma3:1b"
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
    assert "zurich" in prompt
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
        def __init__(self):
            self.choices = []

    def create_empty_choices(*args, **kwargs):
        return EmptyChoicesResponse()

    dummy_client.chat.completions.create = create_empty_choices

    translator_instance = DialectTranslator()
    with pytest.raises(ValueError, match="API returned empty choices"):
        translator_instance.translate_to_dialect("Guten Tag", "bern")


@pytest.mark.parametrize("content", [None, ""])
def test_translate_to_dialect_raises_on_empty_message_content(monkeypatch, content):
    dummy_client = DummyOpenAI("http://localhost:11434/v1", "ollama", 30)
    dummy_client.chat.completions.create = lambda *args, **kwargs: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    monkeypatch.setattr(
        translator,
        "OpenAI",
        lambda base_url, api_key, timeout: dummy_client,
    )

    translator_instance = DialectTranslator()
    with pytest.raises(ValueError, match="empty message content"):
        translator_instance.translate_to_dialect("Guten Tag", "bern")


def test_translate_to_dialect_logs_and_rethrows_api_errors(monkeypatch, caplog):
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
    with (
        caplog.at_level(translator.logging.ERROR),
        pytest.raises(RuntimeError, match="api failure"),
    ):
        translator_instance.translate_to_dialect("Guten Tag", "bern")

    assert "Translation failed for bern" in caplog.text
    assert "api failure" in caplog.text


def test_translate_retries_after_recovering_missing_model(monkeypatch):
    class RecoveringClient(DummyOpenAI):
        def __init__(self, *args):
            super().__init__(*args)
            self.attempts = 0

        def create(self, model, messages, temperature):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("model not found")
            return super().create(model, messages, temperature)

    client = RecoveringClient("http://localhost:11434/v1", "ollama", 30)
    monkeypatch.setattr(
        translator,
        "OpenAI",
        lambda base_url, api_key, timeout: client,
    )
    monkeypatch.setattr(translator, "_has_local_ollama", lambda url: True)
    monkeypatch.setattr(translator, "_is_ollama_server_available", lambda url: True)
    monkeypatch.setattr(
        DialectTranslator,
        "_pull_model_if_missing",
        lambda self: None,
    )

    result = DialectTranslator().translate_to_dialect("Guten Tag", "bern")

    assert result == "üsbersetztä Text"
    assert client.attempts == 2


@pytest.mark.parametrize(
    ("input_text", "target_dialect", "message"),
    [
        ("", "bern", "input_text must be a non-empty string"),
        ("   ", "bern", "input_text must be a non-empty string"),
        (None, "bern", "input_text must be a non-empty string"),
        ("Guten Tag", "", "target_dialect must be a non-empty string"),
        ("Guten Tag", "   ", "target_dialect must be a non-empty string"),
        ("Guten Tag", None, "target_dialect must be a non-empty string"),
    ],
)
def test_translate_to_dialect_validates_inputs(
    monkeypatch, input_text, target_dialect, message
):
    create = lambda *args, **kwargs: pytest.fail("API should not be called")
    monkeypatch.setattr(
        translator,
        "OpenAI",
        lambda base_url, api_key, timeout: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )

    translator_instance = DialectTranslator()
    with pytest.raises(ValueError, match=message):
        translator_instance.translate_to_dialect(input_text, target_dialect)


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
    assert dummy_client.request["model"] == "gemma3:1b"


def test_dialect_translator_uses_configurable_client_and_request_settings(monkeypatch):
    captured = {}

    def fake_openai(base_url, api_key, timeout):
        captured.update(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )
        return DummyOpenAI(base_url, api_key, timeout)

    monkeypatch.setenv("OLLAMA_URL", "http://custom-host:12345/v1")
    monkeypatch.setenv("OLLAMA_API_KEY", "custom-key")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "45")
    monkeypatch.setenv("OLLAMA_MODEL", "custom-model")
    monkeypatch.setenv("OLLAMA_TEMPERATURE", "0.7")
    monkeypatch.setattr(translator, "OpenAI", fake_openai)

    instance = DialectTranslator()
    instance.translate_to_dialect("Guten Morgen", "zurich")

    assert captured == {
        "base_url": "http://custom-host:12345/v1",
        "api_key": "custom-key",
        "timeout": 45,
    }
    assert instance.client.request["model"] == "custom-model"
    assert instance.client.request["temperature"] == 0.7


@pytest.mark.parametrize(
    ("available_models", "expected_status", "expected_message"),
    [
        (["gemma3:1b"], "ready", "Ollama is ready."),
        (
            ["other-model"],
            "unavailable",
            "Configured Ollama model is not installed.",
        ),
    ],
)
def test_get_health_status_checks_configured_model(
    monkeypatch, available_models, expected_status, expected_message
):
    class HealthClient:
        def __init__(self):
            self.models = SimpleNamespace(
                list=lambda: SimpleNamespace(
                    data=[SimpleNamespace(id=model) for model in available_models]
                )
            )

        def with_options(self, **kwargs):
            assert kwargs == {"timeout": 5}
            return self

    monkeypatch.setattr(translator, "_has_local_ollama", lambda url: True)
    monkeypatch.setattr(translator, "_is_ollama_server_available", lambda url: True)
    monkeypatch.setattr(translator, "OpenAI", lambda **kwargs: HealthClient())

    status = DialectTranslator().get_health_status()

    assert status == {
        "status": expected_status,
        "model": "gemma3:1b",
        "message": expected_message,
    }


def test_pull_model_targets_configured_ollama_host(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://remote-ollama:11434/v1")
    monkeypatch.setattr(translator, "_has_local_ollama", lambda url: True)
    monkeypatch.setattr(translator, "_is_ollama_server_available", lambda url: True)
    monkeypatch.setattr(translator, "OpenAI", lambda **kwargs: object())
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return SimpleNamespace(
            returncode=1 if len(commands) == 1 else 0, stdout="", stderr=""
        )

    monkeypatch.setattr(translator.subprocess, "run", fake_run)

    instance = DialectTranslator()
    instance._pull_model_if_missing()

    assert [command for command, _ in commands] == [
        ["ollama", "show", "gemma3:1b"],
        ["ollama", "pull", "gemma3:1b"],
    ]
    assert [kwargs["timeout"] for _, kwargs in commands] == [
        translator.OLLAMA_MODEL_CHECK_TIMEOUT,
        translator.OLLAMA_MODEL_PULL_TIMEOUT,
    ]
    assert all(
        kwargs["env"]["OLLAMA_HOST"] == "http://remote-ollama:11434"
        for _, kwargs in commands
    )


def test_pull_model_recovery_is_unavailable_for_unsupported_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://remote-ollama:11434/custom/v1")
    monkeypatch.setattr(translator, "_has_local_ollama", lambda url: False)
    monkeypatch.setattr(translator, "_is_ollama_server_available", lambda url: True)
    monkeypatch.setattr(translator, "OpenAI", lambda **kwargs: object())
    instance = DialectTranslator()

    with pytest.raises(RuntimeError, match="Automatic Ollama model recovery is unavailable"):
        instance._pull_model_if_missing()


def test_ollama_cli_probe_times_out(monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == translator.OLLAMA_CLI_CHECK_TIMEOUT
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(translator.subprocess, "run", timeout)

    assert not translator._has_local_ollama("http://remote-ollama:11434/v1")


def test_ollama_cli_probe_targets_configured_host(monkeypatch):
    captured = {}

    def successful_list(command, **kwargs):
        captured["command"] = command
        captured["host"] = kwargs["env"]["OLLAMA_HOST"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(translator.subprocess, "run", successful_list)

    assert translator._has_local_ollama("http://remote-ollama:11434/v1")
    assert captured == {
        "command": ["ollama", "list"],
        "host": "http://remote-ollama:11434",
    }


def test_pull_model_check_timeout_is_reported(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://remote-ollama:11434/v1")
    monkeypatch.setattr(translator, "_has_local_ollama", lambda url: True)
    monkeypatch.setattr(translator, "_is_ollama_server_available", lambda url: True)
    monkeypatch.setattr(translator, "OpenAI", lambda **kwargs: object())

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(translator.subprocess, "run", timeout)

    instance = DialectTranslator()
    with pytest.raises(RuntimeError, match="Timed out checking model"):
        instance._pull_model_if_missing()


def test_pull_model_download_timeout_is_reported(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://remote-ollama:11434/v1")
    monkeypatch.setattr(translator, "_has_local_ollama", lambda url: True)
    monkeypatch.setattr(translator, "_is_ollama_server_available", lambda url: True)
    monkeypatch.setattr(translator, "OpenAI", lambda **kwargs: object())
    calls = 0

    def timeout_pull(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return SimpleNamespace(returncode=1)
        assert kwargs["timeout"] == translator.OLLAMA_MODEL_PULL_TIMEOUT
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(translator.subprocess, "run", timeout_pull)

    instance = DialectTranslator()
    with pytest.raises(RuntimeError, match="Timed out pulling model"):
        instance._pull_model_if_missing()
