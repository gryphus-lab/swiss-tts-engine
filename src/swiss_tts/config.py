from pathlib import Path
import json

# Fallback/default texts (kept for backwards compatibility)

# src/swiss_tts/config.py

MODEL_NAME = "swordi/SwissDial-TTS"
DEFAULT_SILENCE_DURATION = 0.2  # Seconds

# Fallback texts if no custom string is passed via parameters
DEFAULT_FALLBACK_TEXTS = {
    "zurich": (
        "Grüezi, min Name isch Abhay Singh. Ich lüüte aa wägenere uusstehende "
        "Genuugtuigszahlig vo CHF 400.00, wo mir im Juni 2024 zuegsproche worde isch. "
        "D Gschäftsnummere isch D-9/2023/10047859. Ich han die Zahlig bis jetzt noned "
        "überchoo und han mi welle nach em Status erkundige."
    ),
    "bern": (
        "Grüessech, oise Name isch Abhay Singh. I lüte a wägenere uusstehende "
        "Genugtuigszahlig vo vierhundert Franke."
    ),
    "basel": (
        "Griezi, mi Name isch Abhay Singh. Ich lüte aa wägenere uusstehende "
        "Genuugtuigszaahlig vo vierhundert Franke."
    )
}


def _normalize_text_value(value):
    if isinstance(value, list):
        return " ".join(s.strip() for s in value if s)
    return value


def _normalize_texts(raw):
    if not isinstance(raw, dict):
        return None
    return {k: _normalize_text_value(v) for k, v in raw.items()}


def _read_json_file(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except Exception:
        return None


def _load_texts_from_json():
    """Look for a JSON file at the repository root and load dialect texts.

    Supported formats:
    - {"zurich": ["sentence1", "sentence2"], "bern": [...]}  # lists of sentences
    - {"zurich": "single long string", ...}  # strings

    If a value is a list it will be joined with a single space.
    """
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [repo_root / "texts.json", repo_root / "config" / "texts.json"]

    for path in candidates:
        raw = _read_json_file(path)
        normalized = _normalize_texts(raw)
        if normalized is not None:
            return normalized
    return None


# Try to load texts from JSON (allows lists of sentences), otherwise keep defaults
_json_texts = _load_texts_from_json()
if _json_texts:
    DEFAULT_TEXTS = _json_texts
else:
    DEFAULT_TEXTS = DEFAULT_FALLBACK_TEXTS
