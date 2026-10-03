import logging
import os
import subprocess
from urllib.parse import urlsplit

from dotenv import load_dotenv
from openai import APIError, OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

OLLAMA_CLI_CHECK_TIMEOUT = 5
OLLAMA_MODEL_CHECK_TIMEOUT = 10
OLLAMA_MODEL_PULL_TIMEOUT = 600


def _ollama_cli_host(url: str) -> str | None:
    """Return a CLI-compatible Ollama host for a standard OpenAI endpoint URL."""
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path.rstrip("/") not in {"", "/v1"}
        or parsed.query
        or parsed.fragment
    ):
        return None

    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://{host}"


def _has_local_ollama(url: str) -> bool:
    """Return True when the Ollama CLI can reach the configured endpoint."""
    host = _ollama_cli_host(url)
    if host is None:
        return False
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False,
            timeout=OLLAMA_CLI_CHECK_TIMEOUT,
            env={**os.environ, "OLLAMA_HOST": host},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _is_ollama_server_available(url: str) -> bool:
    """Check whether the configured Ollama OpenAI-compatible endpoint is reachable."""
    from urllib.error import URLError

    try:
        import urllib.request

        request = urllib.request.Request(
            url.rstrip("/") + "/models",
            headers={"Authorization": "Bearer ollama"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except (URLError, TimeoutError, ValueError):
        return False


class DialectTranslator:
    def __init__(self):
        """
        Initialize the translator with a connection to a local Ollama server.

        The Ollama server URL can be configured via the OLLAMA_URL environment variable,
        defaulting to http://localhost:11434/v1 if not set.
        """
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
        self.ollama_url = ollama_url
        api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        timeout = float(os.getenv("OLLAMA_TIMEOUT", "30"))
        self.model = os.getenv("OLLAMA_MODEL", "gemma3:1b")
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))

        if not _has_local_ollama(ollama_url):
            logger.warning(
                "OLLAMA CLI cannot reach the configured endpoint; automatic model recovery may be unavailable."
            )
        if not _is_ollama_server_available(ollama_url):
            logger.warning(
                "Ollama endpoint %s is not reachable right now; translation requests will fail until the server is started.",
                ollama_url,
            )

        # Point the standard OpenAI client to your local Ollama server
        self.client = OpenAI(base_url=ollama_url, api_key=api_key, timeout=timeout)

    def get_health_status(self) -> dict[str, str]:
        """Report whether the configured Ollama endpoint and model are available."""
        try:
            response = self.client.with_options(timeout=5).models.list()
        except APIError:
            return {
                "status": "unavailable",
                "model": self.model,
                "message": "Ollama endpoint is unreachable.",
            }

        if not any(model.id == self.model for model in response.data):
            return {
                "status": "unavailable",
                "model": self.model,
                "message": "Configured Ollama model is not installed.",
            }

        return {"status": "ready", "model": self.model, "message": "Ollama is ready."}

    def _pull_model_if_missing(self) -> None:
        """Try to fetch the configured Ollama model when it is not yet installed."""
        host = _ollama_cli_host(self.ollama_url)
        if host is None:
            raise RuntimeError(
                "Automatic Ollama model recovery is unavailable for configured URL "
                f"'{self.ollama_url}'; install model '{self.model}' on that endpoint manually."
            )
        env = {**os.environ, "OLLAMA_HOST": host}
        try:
            result = subprocess.run(
                ["ollama", "show", self.model],
                capture_output=True,
                text=True,
                check=False,
                timeout=OLLAMA_MODEL_CHECK_TIMEOUT,
                env=env,
            )
            if result.returncode == 0:
                return
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Timed out checking model '{self.model}' on Ollama endpoint '{host}'."
            ) from exc
        except FileNotFoundError:
            raise RuntimeError(
                "Local Ollama is not installed or not available on PATH. "
                f"Install Ollama, set OLLAMA_HOST to '{host}', and run "
                f"'ollama pull {self.model}'."
            ) from None

        try:
            pull = subprocess.run(
                ["ollama", "pull", self.model],
                capture_output=True,
                text=True,
                check=False,
                timeout=OLLAMA_MODEL_PULL_TIMEOUT,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Timed out pulling model '{self.model}' from Ollama endpoint '{host}'."
            ) from exc
        except FileNotFoundError:
            raise RuntimeError(
                "Local Ollama is not installed or not available on PATH. "
                f"Install Ollama, set OLLAMA_HOST to '{host}', and run "
                f"'ollama pull {self.model}'."
            ) from None
        if pull.returncode != 0:
            stderr = (pull.stderr or pull.stdout or "").strip()
            raise RuntimeError(
                f"Could not load Ollama model '{self.model}' from '{host}'. "
                f"Set OLLAMA_HOST to that URL and run 'ollama pull {self.model}' "
                f"manually. {stderr}"
            )

    def _request_translation(self, prompt: str, target_dialect: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        if not response.choices:
            raise ValueError("API returned empty choices")

        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ValueError("API response contained empty message content")

        translated_text = content.strip()
        logging.info(  # noqa: LOG015 - preserve application-wide logging configuration
            "Translated to %s (length: %s characters)",
            target_dialect,
            len(translated_text),
        )
        return translated_text

    def translate_to_dialect(self, input_text: str, target_dialect: str) -> str:
        """
        Translate text to a specified Swiss German dialect in phonetic form.

        The function accepts input text in any language and produces output with numbers spelled out as words.

        Parameters:
            target_dialect (str): The target Swiss German dialect name.

        Returns:
            str: The translated text in phonetic form with numbers spelled out as words.

        Raises:
            ValueError: If the API response contains no valid choices.
        """
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("input_text must be a non-empty string")
        if not isinstance(target_dialect, str) or not target_dialect.strip():
            raise ValueError("target_dialect must be a non-empty string")

        logging.info(  # noqa: LOG015 - preserve application-wide logging configuration
            "🌍 Translating to %s via Local AI...", target_dialect.upper()
        )

        prompt = f"""
        You are an expert in Swiss German dialects.
        Translate the following standard High German text into the '{target_dialect}' Swiss German dialect.
        The input text may be in English, High German, or any other language.

        CRITICAL RULES:
        1. Write the dialect PHONETICALLY so a text-to-speech engine can read it accurately.
        2. Spell out numbers entirely as words (e.g., 'vierhundert' instead of '400').
        3. Output ONLY the translated text. No explanations, no markdown, no quotes.

        Text to translate:
        {input_text}
        """

        try:
            return self._request_translation(prompt, target_dialect)
        except Exception as exc:
            if "model" not in str(exc).lower() or "not found" not in str(exc).lower():
                logging.exception(  # noqa: LOG015 - preserve application-wide logging configuration
                    "Translation failed for %s", target_dialect
                )
                raise

        try:
            self._pull_model_if_missing()
        except Exception as recovery_error:
            logger.exception("Automatic model recovery failed for %s", self.model)
            raise RuntimeError(
                f"Automatic recovery for Ollama model '{self.model}' failed: "
                f"{recovery_error}"
            ) from recovery_error

        try:
            return self._request_translation(prompt, target_dialect)
        except Exception:
            logging.exception(  # noqa: LOG015 - preserve application-wide logging configuration
                "Translation failed after model recovery for %s", target_dialect
            )
            raise
