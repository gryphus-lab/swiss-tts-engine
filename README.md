# swiss-tts-engine

A multi-dialect Swiss German Text-to-Speech engine built on ESPnet.

This repository provides a simple runtime wrapper around the `swordi/SwissDial-TTS` model and generates waveform files for Swiss German dialect samples.

## Features

- Uses ESPnet's TTS inference pipeline
- Supports Swiss German dialect samples for `zurich`, `bern`, and `basel`
- Produces WAV output files in `audio_output/`
- Built for Python `3.12`

## Requirements

- Python 3.12
- `uv` for the workspace environment
- `espnet`, `espnet-model-zoo`, `torch`, `torchaudio`, `numpy`, `soundfile`

Dependencies are declared in `pyproject.toml`.

## Setup

From the repository root:

```bash
uv sync
```

This will create a local `.venv` and install the required dependencies.

## Run the engine

Use the provided task or run the module directly:

```bash
uv run python -m src.swiss_tts.main
```

or once the environment is active:

```bash
source .venv/bin/activate
python -m src.swiss_tts.main
```

## Output

Generated audio files are written to:

- `audio_output/zurich_speech.wav`
- `audio_output/bern_speech.wav`
- `audio_output/basel_speech.wav`

The engine processes each example sentence from `src/swiss_tts/config.py` and adds a short silence segment between sentences.

## Configuration

Key settings are defined in `src/swiss_tts/config.py`:

- `MODEL_NAME` – model identifier used by ESPnet ModelDownloader
- `DEFAULT_TEXTS` – sample dialect text entries
- `DEFAULT_SILENCE_DURATION` – silence length inserted between sentences

To change the dialect examples, edit `DEFAULT_TEXTS`.

## Mise

This project uses `mise` for workspace and task management. The `mise.toml` configuration includes environment setup and useful commands for working with the project.

- Automatic Python virtual environment: `.venv`
- Local environment path: `.venv/bin`
- Default Python version: `3.12`
- Define tasks for setup, dependency management, linting, formatting, testing, and running the app

## Mise Commands

Quick `mise` commands you can run from the repository root:

- `mise tasks` — list available tasks (alias: `uv tasks`)
- `mise run <task>` — run a specific task defined in `mise.toml` (examples below)
- `mise run setup` — create the local venv and install dependencies
- `mise run generate` or `mise run run` — generate speech audio
- `mise run test` — run the test suite
- `mise run lint` — run lint checks with Ruff
- `mise run format` — format the code with Ruff

Examples:

```bash
# list tasks
mise tasks

# install and sync dependencies
mise run setup

# generate speech output
mise run generate
```

## Tasks

The repository includes useful `uv` tasks in `mise.toml`:

- `uv sync` — install dependencies and create the local virtual environment
- `uv add <package>` — add a new dependency
- `uv sync --upgrade` — update dependencies
- `uv run ruff check .` — lint the code
- `uv run ruff format .` — format the code
- `uv run pytest` — run tests
- `uv run check` — run linting and tests
- `uv run python -m src.swiss_tts.main` — generate speech output
- `uv run run` — alias for the speech generation task

## Notes

- The audio generation runs on CPU by default.
- Warnings from third-party libraries are suppressed in the app.

## License

Specify the license you want to use for this project here.

## CI and SonarQube

This repository includes a GitHub Actions workflow to run tests and (optionally) perform a SonarQube scan: [.github/workflows/sonar.yml](.github/workflows/sonar.yml).

- The workflow installs `uv`, runs `uv sync` to install project dependencies, and executes the test suite with `uv run pytest -q`.
- To enable the SonarQube scan, set these repository secrets in GitHub (Settings → Secrets):
	- `SONAR_TOKEN` — SonarQube authentication token.
	- `SONAR_PROJECT_KEY` — Sonar project key.
	- Optional: `SONAR_HOST_URL` — SonarQube server URL for self-hosted Sonar (set only if needed).

If the Sonar secrets are not provided the workflow will still run tests and will skip the Sonar scan with a helpful message.

## Testing notes

- Tests use `pytest`. Run them locally via:

```bash
uv run pytest -q
```

- Deprecation warnings from third-party packages (e.g. `distutils` and `pkg_resources`) are filtered using `pytest.ini` to keep the test output focused on relevant failures. See `pytest.ini` in the repository root.

