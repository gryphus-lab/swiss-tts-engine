# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A monorepo for a multi-dialect Swiss German Text-to-Speech system, split into two halves:

- **Python backend** (`apps/swiss-tts-engine/src/swiss_tts/`) — an ESPnet-based TTS engine plus a FastAPI REST service. Managed by `uv` / `mise`.
- **Expo / React Native mobile app** (`apps/swiss-tts-app/`) — a thin client that POSTs text to the backend and plays back the returned `.wav`. Managed by `npm`.

The two are wired together at runtime over HTTP, and together in `docker-compose.yml` for local end-to-end dev.

## Commands

Tasks are defined in `mise.toml` and run both halves. `mise run setup` does `uv sync` **and** `npm install`; `mise run test`/`lint`/`format` run the Python and JS toolchains together.

```bash
mise run setup            # uv sync + npm install
mise run test             # pytest (with coverage) + jest
mise run lint             # prettier --check + ruff check
mise run format           # prettier --write + ruff format
mise run generate         # run the CLI pipeline (alias: gen)
mise run check            # ruff check + pytest (no JS)
```

### Backend (Python)

```bash
uv run pytest                                                        # all Python tests
uv run pytest tests/test_api.py                                     # one file
uv run pytest tests/test_api.py::test_health_check                  # one test
uv run pytest --cov=swiss_tts --cov-report=xml:coverage.xml         # with coverage (matches CI/Sonar)
uv run ruff check . && uv run ruff format .
uv run python -m swiss_tts.main                                     # run the translate→synthesize CLI pipeline
uv run uvicorn swiss_tts.api:app --reload --port 8000               # run the REST API
```

Tests import the package as `swiss_tts`, which works because `uv sync` installs it editable per `pyproject.toml` (`tool.hatch.build` → `src/swiss_tts`). Run `uv sync` before testing if imports fail.

### Frontend (Expo)

```bash
npm test                  # jest --coverage (jest-expo preset)
npm run lint              # prettier --check .  (this is the "lint" — there is no ESLint)
npm start --prefix apps/swiss-tts-app  # expo start
```

Frontend tests live in `apps/swiss-tts-app/__tests__/`.

### Full-stack via Docker

```bash
./dev.sh                  # auto-detects HOST_IP, then docker-cleanup + compose up + tails app logs
```

`HOST_IP` must be set for compose (it feeds both `EXPO_PUBLIC_API_IP` and the Expo packager hostname). `dev.sh` detects it automatically on macOS/Linux. Docker tasks: `mise run docker-build`, `docker-compose`, `docker-cleanup`, `docker-app-logs`.

## Architecture

### Backend pipeline

The core flow is **translate → synthesize**, implemented across three modules:

1. `translator.py` — `DialectTranslator` calls a **local Ollama** server (OpenAI-compatible client pointed at `OLLAMA_URL`, default `http://localhost:11434/v1`) to rewrite arbitrary input text into phonetic Swiss German for a target dialect. The model name is hardcoded in the prompt call.
2. `main.py` — `SwissTTSEngine` wraps ESPnet: it downloads `config.MODEL_NAME` (`swordi/SwissDial-TTS`) via `ModelDownloader`, runs `Text2Speech` inference on **CPU**, splits text into sentences, inserts silence padding between them, and writes a `{dialect}_speech.wav` into `audio_output/`. `run_translation_pipeline()` ties translator + engine together for the CLI.
3. `api.py` — FastAPI app exposing the pipeline. Models are loaded **lazily in a background thread** at startup (`lifespan`) and stored in a module-level `models` dict, so the server accepts connections immediately and returns `503` from `/health` and `/api/v1/synthesize` until loading finishes (or reports the failure stored under `models["error"]`).

Key endpoints: `GET /health`, `POST /api/v1/synthesize` (`{text, dialect}` → translated text + audio URL), `GET /api/v1/audio/{filename}` (serves WAVs, with path-traversal guarding via `os.path.basename` + abspath containment check), `GET /` (serves `public/index.html`).

### Config & dialect text

- `SUPPORTED_DIALECTS = ["zurich", "bern", "basel"]` is the single source of truth, validated in both `main.py` and `api.py`.
- `config.py` builds `DEFAULT_TEXTS` at import time: it first tries `texts.json` at the repo root, then `config/texts.json`. Each file is normalized (lists of sentences are joined; empty/invalid entries dropped); malformed JSON is silently ignored and `DEFAULT_FALLBACK_TEXTS` is used. These are fallback/sample texts only — the live API/CLI path translates user input, it does not read `DEFAULT_TEXTS`.

### Frontend

`apps/swiss-tts-app/App.js` is a single-screen component: text box + dialect Picker + a button that POSTs to `${EXPO_PUBLIC_API_IP}:8000/api/v1/synthesize` and plays the WAV via `expo-av`. **`EXPO_PUBLIC_API_IP` is required** — the app throws at module load if it's unset. Audio URLs get a `?t=Date.now()` cache-buster.

`metro.config.js` sets `unstable_enablePackageExports = false` (needed for Node 20+ compatibility) — don't remove it.

## Conventions & gotchas

- **`apps/swiss-tts-app/AGENTS.md` (loaded via its `CLAUDE.md`) instructs: read the versioned Expo docs at the pinned version before writing Expo/React Native code.** This project tracks Expo SDK 54 (`package.json`). Honor that — Expo APIs change between SDK versions.
- Two test ecosystems, two coverage reports: `coverage.xml` (Python, consumed by SonarQube) and `coverage/` (jest). Sonar scans `apps/swiss-tts-engine/src` + `apps/swiss-tts-app` and excludes `metro.config.js` and `**/__tests__/*.js`.
- CI (`.github/workflows/ci.yml`) runs `mise run setup` then `mise run test` then a SonarQube scan (skips gracefully without `SONAR_TOKEN`). A separate `trivy.yml` builds the Docker image and scans it.
- In Docker, the backend reaches Ollama on the host via `OLLAMA_URL=http://host.docker.internal:11434/v1`; the ESPnet model cache is persisted in the `espnet_model_cache` volume to avoid re-downloading ~700MB on restart.
