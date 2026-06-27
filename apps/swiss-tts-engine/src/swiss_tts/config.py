from pathlib import Path
import json


# The default dialects our engine supports and wants to generate
SUPPORTED_DIALECTS = ["zurich", "bern", "basel"]

MODEL_NAME = "swordi/SwissDial-TTS"
DEFAULT_SILENCE_DURATION = 0.2  # Seconds

# Fallback texts if no custom string is passed via parameters
DEFAULT_FALLBACK_TEXTS = {
    "zurich": (
        "Grüezi, min Name isch Abhay Singh. Ich lüüte aa wägenere uusstehende "
        "Genuugtuigszahlig vo vierhundert Franke."
    ),
    "bern": (
        "Grüessech, oise Name isch Abhay Singh. I lüte a wägenere uusstehende "
        "Genugtuigszahlig vo vierhundert Franke."
    ),
    "basel": (
        "Griezi, mi Name isch Abhay Singh. Ich lüte aa wägenere uusstehende "
        "Genuugtuigszaahlig vo vierhundert Franke."
    ),
}


def _normalize_text_value(value):
    """
    Join list elements into a single string, or return the value unchanged if not a list.

    Returns:
        A space-separated string if the input is a list, otherwise the original value.
    """
    if isinstance(value, list):
        result = " ".join(s.strip() for s in value if isinstance(s, str) and s.strip())
        return result if result.strip() else None
    return value if (isinstance(value, str) and value.strip()) else None


def _normalize_texts(raw):
    """
    Normalize each value in a dictionary.

    Returns a new dictionary with each value normalized via _normalize_text_value,
    or None if the input is not a dictionary.

    Parameters:
        raw: The value to normalize.

    Returns:
        A normalized dictionary, or None if input is not a dictionary.
    """
    if not isinstance(raw, dict):
        return None
    result = {}
    for k, v in raw.items():
        if isinstance(v, (str, list)):
            result[k] = _normalize_text_value(v)
    return result if result else None


def _read_json_file(path):
    """
    Read and parse a JSON file.

    Parameters:
        path: A pathlib.Path object pointing to the JSON file.

    Returns:
        The parsed JSON object, or None if the file does not exist or cannot be parsed.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except Exception:
        return None


def _load_texts_from_json():
    """
    Load dialect text configuration from an optional JSON file.

    Returns:
        dict or None: A mapping of dialect names to text strings, or None if
            no configuration file is found.
    """
    app_root = Path(__file__).resolve().parents[2]
    candidates = [app_root / "texts.json", app_root / "config" / "texts.json"]

    for path in candidates:
        raw = _read_json_file(path)
        normalized = _normalize_texts(raw)
        if normalized is not None:
            return normalized
    return None


# Try to load texts from JSON (allows lists of sentences), otherwise keep defaults
_json_texts = _load_texts_from_json()
if _json_texts is not None:
    DEFAULT_TEXTS = _json_texts
else:
    DEFAULT_TEXTS = DEFAULT_FALLBACK_TEXTS
