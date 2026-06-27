# swiss-tts-engine

Python backend app for Swiss German dialect translation and text-to-speech synthesis.

## Run

From the repository root:

```bash
uv sync --all-packages
uv run --package swiss-tts-engine python -m swiss_tts.main
```

Run the API:

```bash
uv run --package swiss-tts-engine uvicorn swiss_tts.api:app --reload --port 8000
```

## Test

```bash
uv run --package swiss-tts-engine pytest apps/swiss-tts-engine/tests
```
