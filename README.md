# Swiss TTS Engine

A monorepo for a Swiss German text-to-speech system that translates arbitrary input text into Swiss German dialects, synthesizes speech with an ESPnet model, and exposes the result through a FastAPI backend and a React Native / Expo client.

## What it does

This project turns standard text into local Swiss German audio in three steps:

1. Translate the input into a dialect-specific phonetic Swiss German variant using a local Ollama-backed LLM.
2. Generate WAV audio with an ESPnet TTS model.
3. Serve the result through a REST API and play it back in the mobile app.

The system currently supports these dialects:

- Zurich
- Bern
- Basel

## Tech stack

### Backend

- Python 3.12+
- FastAPI for the REST API
- ESPnet and espnet-model-zoo for speech synthesis
- PyTorch / torchaudio for inference
- OpenAI Python client pointed to a local Ollama endpoint
- SoundFile + NumPy for audio I/O

### Mobile app

- Expo / React Native
- React Native Picker for dialect selection
- expo-av and expo-file-system for audio playback and local file handling
- Jest + React Native Testing Library for frontend tests

### Tooling

- uv for Python dependency management
- npm for the app front end
- mise for project tasks and orchestration
- Docker Compose for full-stack local deployment

## Solution architecture

```text
User text
   ↓
DialectTranslator
   └─ local Ollama / OpenAI-compatible endpoint (gemma4)
         ↓ "phonetic Swiss German text"
SwissTTSEngine
   └─ ESPnet TTS model download + CPU inference
         ↓ generated .wav
FastAPI API
   ├─ /health
   ├─ /api/v1/synthesize
   └─ /api/v1/audio/{filename}
         ↓
Expo / React Native mobile app
   └─ plays returned audio
```

## Main functionalities

- Translate input text into Swiss German dialect speech form
- Generate dialect-specific speech files in the `audio_output/` directory
- Expose a health endpoint and a synthesis endpoint for clean service integration
- Return audio URLs that are served securely from the backend
- Support local batch generation for multiple dialects in one run
- Provide a mobile UI for entering text, choosing a dialect, and playing the result
- Run both backend and frontend together with Docker Compose

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
├── docker-compose.yml
├── Dockerfile
├── dev.sh
├── mise.toml
├── pyproject.toml
├── pytest.ini
├── README.md
├── sonar-project.properties
└── uv.lock
```

## Prerequisites

- Python 3.12+
- Node.js / npm
- uv
- Docker (optional, for full-stack local deployment)
- Local Ollama instance running at `http://localhost:11434/v1` by default

If Ollama is running elsewhere, set:

```bash
export OLLAMA_URL=http://your-host:11434/v1
```

For the Expo app, set the backend origin (without a path), for example:

```bash
export EXPO_PUBLIC_API_IP=http://192.168.1.10
```

The app appends `:8000/api/v1/synthesize` to this origin before each request.

## Quick start

Install all dependencies:

```bash
mise run setup
```

Or install manually:

```bash
uv sync --all-packages
npm install --prefix apps/swiss-tts-app
```

## Run the backend

Start the text-to-speech generation pipeline directly:

```bash
mise run generate
```

Start the FastAPI service:

```bash
uv run --package swiss-tts-engine uvicorn swiss_tts.api:app --reload --port 8000
```

The backend serves a small HTML frontend from `apps/swiss-tts-engine/public/index.html` and exposes the following HTTP endpoints:

- `GET /health` — checks if the engine and translator are ready
- `POST /api/v1/synthesize` — accepts `{ text, dialect }` and returns a generated audio URL
- `GET /api/v1/audio/{filename}` — serves generated WAV files
- `GET /` — serves the local frontend page

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"text":"Guten Tag, mein Name ist Abhay Singh.","dialect":"zurich"}'
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

## Notes and gotchas

- The backend loads the ESPnet model and translator lazily in a background thread so the API starts quickly.
- Requests return `503` until both model loaders are ready.
- The backend validates the requested dialect against the supported list in `config.py`.
- Audio files are written into `audio_output/` and served back to clients.
- The translator is intentionally phonetic: numbers are spelled out as words to make generated speech more natural for TTS.

## Common project commands

```bash
mise run setup
mise run generate
mise run test
mise run lint
mise run format
mise run check
```

The project is designed as a lightweight local Swiss German speech pipeline with a strong emphasis on dialect-aware translation and easy local orchestration.
