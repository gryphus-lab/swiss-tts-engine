# Swiss TTS Engine

A monorepo for a Swiss German text-to-speech pipeline that translates arbitrary text into Swiss German dialects, synthesizes speech with an ESPnet model, and exposes the result through a FastAPI backend and a React Native / Expo client.

## Overview

The project turns standard text into local Swiss German audio in three steps:

1. Translate the input into a dialect-specific phonetic Swiss German variant through a local Ollama-backed language model.
2. Generate `.wav` output with an ESPnet TTS model.
3. Serve the result through a REST API and play it back in the mobile app.

Supported dialects:

- Zurich
- Bern
- Basel

## Recent updates

- Added lazy backend startup with background model loading so the API responds immediately while ESPnet and Ollama initialization runs in the background.
- Added health checks for the translator backend, including availability and model detection checks.
- Added automatic Ollama model recovery when the configured model is missing.
- Added dialect validation and safer audio serving with path traversal guards.
- Added Expo app configuration using `EXPO_PUBLIC_API_IP` and a timestamp cache-buster on audio URLs.
- Added repo-level orchestration via `mise` for setup, testing, Docker, and generation tasks.

## Tech stack

### Backend

- Python 3.12+
- FastAPI
- ESPnet + espnet-model-zoo
- PyTorch / torchaudio
- OpenAI Python client pointed to a local Ollama endpoint
- SoundFile + NumPy

### Mobile app

- Expo / React Native
- `@react-native-picker/picker` for dialect selection
- `expo-av` for playback
- `expo-file-system` and local file handling
- Jest + React Native Testing Library

### Tooling

- `uv` for Python dependencies and project environment management
- `npm` for the Expo app
- `mise` for local task orchestration
- Docker Compose for local full-stack deployment

## Architecture

```text
User text
   ↓
DialectTranslator
   └─ local Ollama / OpenAI-compatible endpoint (gemma3:1b by default)
         ↓ phonetic Swiss German text
SwissTTSEngine
   └─ ESPnet TTS model download + CPU inference
         ↓ generated WAV file
FastAPI API
   ├─ /health
   ├─ /api/v1/synthesize
   ├─ /api/v1/audio/{filename}
   └─ /
         ↓
Expo / React Native app
   └─ plays returned audio
```

## Repository layout

```text
.
├── apps/
│   ├── swiss-tts-engine/
│   │   ├── src/swiss_tts/
│   │   │   ├── api.py
│   │   │   ├── config.py
│   │   │   ├── main.py
│   │   │   └── translator.py
│   │   ├── tests/
│   │   ├── public/
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── swiss-tts-app/
│       ├── App.js
│       ├── __tests__/
│       ├── app.json
│       ├── package.json
│       └── README/docs files
├── audio_output/
├── .github/
├── components/
├── docker-compose.yml
├── Dockerfile
├── dev.sh
├── mise.toml
├── pyproject.toml
├── pytest.ini
├── README.md
├── sonar-project.properties
├── uv.lock
└── .env.example (if present in your local setup)
```

## Prerequisites

- Python 3.12+
- Node.js and npm
- `uv`
- Docker (optional, for full-stack local deployment)
- Local Ollama instance running at `http://localhost:11434/v1` by default

### Configure environment variables

If Ollama is running elsewhere, set:

```bash
export OLLAMA_URL=http://your-host:11434/v1
```

Optional translator settings:

```bash
export OLLAMA_MODEL=gemma3:1b
export OLLAMA_API_KEY=ollama
export OLLAMA_TIMEOUT=30
export OLLAMA_TEMPERATURE=0.3
```

For the Expo app, set the backend origin without a path:

```bash
export EXPO_PUBLIC_API_IP=http://192.168.1.10
```

The app appends `:8000/api/v1/synthesize` to this origin before each request.

## Quick start

Install everything with the repo helper:

```bash
mise run setup
```

Or install manually:

```bash
uv sync --all-packages
npm install --prefix apps/swiss-tts-app
```

## Run the backend

Generate speech directly from the CLI pipeline:

```bash
mise run generate
```

Equivalent direct command:

```bash
uv run --package swiss-tts-engine python -m swiss_tts.main
```

Start the FastAPI service:

```bash
uv run --package swiss-tts-engine uvicorn swiss_tts.api:app --reload --port 8000
```

The backend serves a small HTML frontend from `apps/swiss-tts-engine/public/index.html` and exposes the following endpoints:

- `GET /health` — checks whether the engine and translator are ready
- `POST /api/v1/synthesize` — accepts `{ text, dialect }` and returns generated audio metadata plus an audio URL
- `GET /api/v1/audio/{filename}` — serves generated WAV files
- `GET /` — serves the local frontend page

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Guten Tag, mein Name ist Abhay Singh.","dialect":"zurich"}'
```

Example response:

```json
{
  "status": "success",
  "dialect": "zurich",
  "translated_text": "...",
  "audio_url": "/api/v1/audio/zurich_speech.wav"
}
```

## Run the mobile app

From the repo root:

```bash
npm run start --prefix apps/swiss-tts-app
```

The app lets the user:

- enter arbitrary text
- choose a target dialect
- send the text to the backend
- listen to the generated speech immediately

## Docker

Build and run the full stack with Docker Compose:

```bash
./dev.sh
```

Or run the project commands directly:

```bash
mise run docker-build
mise run docker-compose
```

The API is exposed on port `8000` and the Expo app on port `8081`.

The Docker setup also uses the `espnet_model_cache` volume so the ESPnet model is reused and not re-downloaded on each restart.

## Testing

Run the full configured test suites:

```bash
mise run test
```

Run only Python tests:

```bash
uv run --package swiss-tts-engine pytest apps/swiss-tts-engine/tests --cov=swiss_tts --cov-report=xml:coverage.xml
```

Run only mobile tests:

```bash
npm run test --prefix apps/swiss-tts-app
```

Run lint/format checks:

```bash
mise run lint
mise run format
```

## Notes and gotchas

- The backend loads the ESPnet model and translator lazily in a background thread so the API starts quickly.
- Requests return `503` until both model loaders are ready.
- The backend validates the requested dialect against the supported list in `config.py`.
- Audio files are written into `audio_output/` and served back to clients.
- The translator is intentionally phonetic: numbers are spelled out as words to make generated speech more natural for TTS.
- The front end requires `EXPO_PUBLIC_API_IP` to be set before launch; otherwise it throws at module load.
- The local Ollama endpoint is expected to be reachable from the backend; if the model is missing, the code attempts a local `ollama pull` when possible.

## Common commands

```bash
mise run setup
mise run generate
mise run test
mise run lint
mise run format
mise run check
```

## Project intent

This repository is a lightweight local Swiss German speech pipeline with a strong emphasis on dialect-aware translation, CPU-based speech synthesis, and straightforward local orchestration for development and demos.
