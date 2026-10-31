# Versioning

This monorepo uses [Semantic Versioning](https://semver.org):
**MAJOR.MINOR.PATCH**, baselined at **1.0.0**.

One version covers the whole repo (the Python engine/API and the Expo app ship
together). It lives in several files that must stay in lockstep; a CI check
(`scripts/check_version.py`, wired into `mise run test`) fails the build if they
drift.

## Version surfaces

| File | Field | Purpose |
|------|-------|---------|
| `pyproject.toml` | `project.version` | monorepo |
| `apps/swiss-tts-engine/pyproject.toml` | `project.version` | engine package — read back by the FastAPI app so the running API self-identifies (OpenAPI/`/docs` + `/health`) |
| `apps/swiss-tts-app/package.json` | `version` | Expo app (npm) |
| `apps/swiss-tts-app/app.json` | `expo.version` | Expo app; also `expo.android.versionCode` and `expo.ios.buildNumber` |

`versionCode` / `buildNumber` are derived from the semver as
`MAJOR*1_000_000 + MINOR*10_000 + PATCH` (monotonic, with ample room for the
repo's high patch cadence). For `1.7.76` that is **`1070076`**.

The REST API reports its version via standard package metadata, so a deployed
service answers `GET /health` with its exact `version` and shows it in `/docs`.

## When to bump

Bump the version on every change merged to `main`, by the highest-impact change
in the PR:

| Change | Bump | Example |
|--------|------|---------|
| Breaking — removed/renamed API route, response-shape break, incompatible model change | **MAJOR** | `feat!:` / `BREAKING CHANGE:` |
| New backward-compatible capability | **MINOR** | REST API, web UI, Expo app, EAS/APK build config |
| Bug fix, build/CI/config, refactor, chore, docs, generated tests | **PATCH** | `fix:`, lint/format, CI, README |

### Dependabot updates

Classify by impact on the product, not by the dependency's own version jump. A
routine library bump does **not** change what the app does for a user, so by
default:

- **Any Dependabot bump → PATCH** (build/dev-tooling *and* runtime libs:
  fastapi, uvicorn, openai, torch, numpy, espnet, react-native, expo, ruff,
  jest, base images, …).
- Promote to **MINOR** only if the bump is deliberately adopted to expose a new
  product capability (e.g. migrating to a dependency version specifically to
  ship a new feature).
- Promote to **MAJOR** only if the bump forces a breaking change in our own
  public surface (API routes/response shapes).

Rule of thumb: dependency maintenance is PATCH; a change to what the product
*does* is MINOR (or MAJOR if it breaks the public API).

## How the current version was derived

Computed from all **129** PRs merged to `main` from the `1.0.0` baseline. Seven
introduced genuine product capabilities (**MINOR**); the remaining 122
(Dependabot, CodeRabbit-generated tests, lint/format, CI, docs, fixes, reorgs)
are **PATCH**.

The seven MINOR features, in merge order:

| PR | Feature | Version |
|----|---------|---------|
| #5 | Hochdeutsch input before audio generation | 1.1.0 |
| #6 | Dockerized REST API endpoints | 1.2.0 |
| #11 | Web UI for basic functionality | 1.3.0 |
| #14 | Health-check polling + loading indicator | 1.4.0 |
| #18 | New Expo mobile app | 1.5.0 |
| #29 | EAS build configuration | 1.6.0 |
| #53 | APK build configuration | 1.7.0 |

After those, 76 of the 122 patch-level PRs were merged, landing the patch
component at **76**.

**Current version: `1.7.76`** (`versionCode 1070076`).
