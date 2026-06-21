# swiss-tts-engine

A multi-dialect Swiss German Text-to-Speech engine built on ESPnet.

This repository provides a runtime wrapper around the `swordi/SwissDial-TTS` model, with optional Hochdeutsch translation into Swiss German dialects before generating WAV output.

## Features

- Uses ESPnet's TTS inference pipeline
- Translates standard High German (Hochdeutsch) into phonetic Swiss German dialect text
- Supports `zurich`, `bern`, and `basel` dialect samples
- Writes WAV output files to `audio_output/`
- Loads fallback dialect text from `src/swiss_tts/config.py` or optional `texts.json`
- Includes a REST API with FastAPI endpoints for synthesis and audio download
- Includes pytest coverage for `config`, `main`, `translator`, and `api` components

## Requirements

- Python 3.12
- `uv` for the workspace environment
- `espnet`, `espnet-model-zoo`, `torch`, `torchaudio`, `numpy`, `soundfile`, `openai`, `python-dotenv`

Dependencies are declared in `pyproject.toml`.

## Setup

From the repository root:

```bash
uv sync
```

This will create a local `.venv` and install the required dependencies.

## Run the engine

Use the provided `mise` task or run the module directly:

```bash
mise run generate
```

or:

```bash
uv run python -m src.swiss_tts.main
```

If you have activated the virtual environment manually:

```bash
source .venv/bin/activate
python -m src.swiss_tts.main
```

## REST API

Run the REST API server locally with Uvicorn:

```bash
uv run uvicorn src.swiss_tts.api:app --reload --port 8000
```

### API Endpoints

#### Health Check

- **GET** `/health`
  - Returns API status and model readiness
  - Response: `{"status": "ready", "message": "All models loaded and ready."}`

#### Synthesize Speech

- **POST** `/api/v1/synthesize`
  - Translates text to a target dialect and generates audio
  - Request body:

    ```json
    {
      "text": "Your text here",
      "dialect": "zurich",
      "translate": true
    }
    ```

  - `dialect` options: `zurich`, `bern`, `basel`
  - `translate`: Set to `true` if input is Hochdeutsch (standard High German)
  - Response:

    ```json
    {
      "status": "success",
      "dialect": "zurich",
      "translated_text": "translated text in dialect",
      "audio_url": "/api/v1/audio/zurich_speech.wav"
    }
    ```

#### Download Audio File

- **GET** `/api/v1/audio/{filename}`
  - Downloads a generated audio WAV file
  - Path traversal protection prevents directory escape attacks
  - Returns: WAV file with `audio/wav` media type

#### Web UI

- **GET** `/`
  - Serves a simple HTML frontend for interactive speech synthesis
  - Access at `http://localhost:8000`

The included web interface at `public/index.html` provides a user-friendly way to interact with the TTS engine:

- **Text Input** – Enter text in standard High German (Hochdeutsch) or Swiss German
- **Dialect Selection** – Choose from available dialects: Zurich, Bern, or Basel
- **Translation Toggle** – Enable automatic translation from Hochdeutsch to the target dialect
- **Audio Playback** – Listen to the generated speech directly in the browser
- **Download** – Save generated audio files to your device

Simply run the API server and open your browser to `http://localhost:8000`.

## Usage example

To invoke the translation-and-generation pipeline directly from Python:

```python
from swiss_tts.main import run_translation_pipeline

run_translation_pipeline(
    hochdeutsch_input="Guten Tag, ich rufe wegen einer ausstehenden Zahlung an.",
    target_dialects=["zurich", "bern", "basel"],
)
```

## Output

Generated audio files are written to:

- `audio_output/zurich_speech.wav`
- `audio_output/bern_speech.wav`
- `audio_output/basel_speech.wav`

The generator processes each example sentence and inserts a short silence segment between sentences.

## Configuration

Key settings are defined in `src/swiss_tts/config.py`:

- `MODEL_NAME` – ESPnet model identifier used by `ModelDownloader`
- `DEFAULT_TEXTS` – fallback dialect text entries
- `DEFAULT_SILENCE_DURATION` – silence length inserted between sentences

Optional JSON override:

- `texts.json` at the repository root, or
- `config/texts.json`

If present, either file will be loaded and normalized into `DEFAULT_TEXTS`.

## Testing

Run the full test suite with coverage:

```bash
mise run test
```

or directly:

```bash
uv run pytest --cov=swiss_tts --cov-report=xml:coverage.xml
```

The test suite achieves **100% code coverage** across the package. There are comprehensive tests for:

- `tests/test_config.py` – Configuration loading, text normalization, JSON parsing
- `tests/test_main.py` – Speech generation, audio processing, model initialization
- `tests/test_translator.py` – LLM-based dialect translation with Ollama
- `tests/test_api.py` – API endpoints, error handling, model lifecycle
- `tests/test_api_client.py` – Integration tests using FastAPI `TestClient`

When running tests locally, the translator client is mocked so the suite does not require a live OpenAI or Ollama server.

## Mise

This project uses `mise` for workspace and task management.

Available tasks include:

- `mise run setup` — install dependencies and create the local virtual environment
- `mise run test` — run the test suite with coverage
- `mise run lint` — run Ruff linting checks
- `mise run format` — format code with Ruff
- `mise run generate` — generate Swiss German speech audio

## Notes

- Audio generation runs on CPU by default.
- Translator integration uses the local OpenAI-compatible client to hit `http://localhost:11434/v1`.
- Third-party warnings are suppressed in the app for cleaner runtime output.

## Troubleshooting

- If `texts.json` is present, the project loads it from the repository root first.
- If root-level `texts.json` is missing, it falls back to `config/texts.json`.
- Invalid JSON in either file is ignored and the app falls back to the default `DEFAULT_TEXTS` values.

## License

Specify the license you want to use for this project here.

## CI and SonarQube

This repository includes a GitHub Actions workflow to run tests and optionally perform a SonarQube scan.

The CI workflow installs dependencies, runs `uv sync`, and executes the test suite with `uv run pytest -q`.

To enable SonarQube scanning, configure repository secrets:

- `SONAR_TOKEN`
- `SONAR_PROJECT_KEY`
- Optional: `SONAR_HOST_URL`

Without Sonar secrets, CI still runs tests and skips the Sonar scan gracefully.
