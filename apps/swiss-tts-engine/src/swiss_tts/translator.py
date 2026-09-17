import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class DialectTranslator:
    def __init__(self):
        """
        Initialize the translator with a connection to a local Ollama server.

        The Ollama server URL can be configured via the OLLAMA_URL environment variable,
        defaulting to http://localhost:11434/v1 if not set.
        """
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
        api_key = os.getenv("OLLAMA_API_KEY", "ollama")
        timeout = float(os.getenv("OLLAMA_TIMEOUT", "30"))
        self.model = os.getenv("OLLAMA_MODEL", "gemma4")
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))

        # Point the standard OpenAI client to your local Ollama server
        self.client = OpenAI(base_url=ollama_url, api_key=api_key, timeout=timeout)

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
        except Exception:
            logging.exception(  # noqa: LOG015 - preserve application-wide logging configuration
                "Translation failed for %s", target_dialect
            )
            raise
