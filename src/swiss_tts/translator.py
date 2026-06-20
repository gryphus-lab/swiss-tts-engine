# src/swiss_tts/translator.py
from openai import OpenAI

class DialectTranslator:
    def __init__(self):
        # Point the standard OpenAI client to your local Ollama server
        self.client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        
    def translate_to_dialect(self, hochdeutsch_text: str, target_dialect: str) -> str:
        """Translates standard High German into phonetic Swiss German using a local LLM."""
        print(f"🌍 Translating to {target_dialect.upper()} via Local Open-Source AI...")
        
        prompt = f"""
        You are an expert in Swiss German dialects. 
        Translate the following standard High German (Hochdeutsch) text into the '{target_dialect}' Swiss German dialect.
        
        CRITICAL RULES:
        1. Write the dialect PHONETICALLY so a text-to-speech engine can read it accurately.
        2. Spell out numbers entirely as words (e.g., 'vierhundert' instead of '400').
        3. Output ONLY the translated text. No explanations, no markdown, no quotes.
        
        Text to translate:
        {hochdeutsch_text}
        """

        response = self.client.chat.completions.create(
            model="gemma4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        translated_text = response.choices[0].message.content.strip()
        print(f"   ↳ {translated_text}")
        return translated_text