# swiss-tts-engine

Monorepo for a Swiss German text-to-speech system.

## Layout

```text
.
├── apps/
│   ├── swiss-tts-engine/
│   │   ├── src/swiss_tts/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── README.md
│   └── swiss-tts-app/
│       ├── __tests__/
│       ├── App.js
│       ├── app.json
│       ├── package.json
│       └── README/docs files
├── pyproject.toml
├── uv.lock
└── mise.toml
```

## Setup

From the repository root:

```bash
mise run setup
```

or:

```bash
uv sync --all-packages
npm install --prefix apps/swiss-tts-app
```

## Python Backend

Run the speech generation pipeline:

```bash
mise run generate
```

Run the REST API:

```bash
uv run --package swiss-tts-engine uvicorn swiss_tts.api:app --reload --port 8000
```

The backend package lives in `apps/swiss-tts-engine/src/swiss_tts`. Its simple web UI is served from `apps/swiss-tts-engine/public/index.html`.

## Mobile App

Run Expo from the mobile app package:

```bash
npm run start --prefix apps/swiss-tts-app
```

Set `EXPO_PUBLIC_API_IP` to the host running the backend before starting the app.

## Tests

Run all configured test suites:

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

## Docker

Build and run both apps:

```bash
mise run docker-build
mise run docker-compose
```

The API is exposed on port `8000`; Expo is exposed on port `8081`.
