#!/usr/bin/env python3
"""Verify the semantic version is identical across every version surface.

The monorepo keeps one semantic version (see /VERSIONING.md). It is written in
several files; this script fails (exit 1) if any of them disagree, so drift is
caught in CI instead of shipping mismatched artifacts.

Surfaces checked:
  - pyproject.toml                              (monorepo)
  - apps/swiss-tts-engine/pyproject.toml        (engine package -> FastAPI version)
  - apps/swiss-tts-app/package.json             (Expo app, npm)
  - apps/swiss-tts-app/app.json                 (Expo app; also versionCode/buildNumber)

Run:  uv run python scripts/check_version.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _toml_version(path: Path) -> str:
    with path.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _json_version(path: Path, *keys: str) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        data = data[key]
    return data


def expected_version_code(semver: str) -> int:
    """MAJOR*1_000_000 + MINOR*10_000 + PATCH (monotonic, lots of patch room)."""
    major, minor, patch = (int(p) for p in semver.split("."))
    return major * 1_000_000 + minor * 10_000 + patch


def main() -> int:
    surfaces = {
        "pyproject.toml": _toml_version(ROOT / "pyproject.toml"),
        "apps/swiss-tts-engine/pyproject.toml": _toml_version(
            ROOT / "apps/swiss-tts-engine/pyproject.toml"
        ),
        "apps/swiss-tts-app/package.json": _json_version(
            ROOT / "apps/swiss-tts-app/package.json", "version"
        ),
        "apps/swiss-tts-app/app.json": _json_version(
            ROOT / "apps/swiss-tts-app/app.json", "expo", "version"
        ),
    }

    semver_re = re.compile(r"^\d+\.\d+\.\d+$")
    versions = set(surfaces.values())
    errors: list[str] = []

    if len(versions) != 1:
        errors.append("Version mismatch across surfaces:")
        for name, ver in surfaces.items():
            errors.append(f"    {ver:<12} {name}")
    else:
        (semver,) = versions
        if not semver_re.match(semver):
            errors.append(f"Version '{semver}' is not valid MAJOR.MINOR.PATCH.")
        else:
            # Expo versionCode / iOS buildNumber must match the derivation.
            app_json = json.loads(
                (ROOT / "apps/swiss-tts-app/app.json").read_text(encoding="utf-8")
            )
            expo = app_json["expo"]
            want = expected_version_code(semver)
            got_android = expo.get("android", {}).get("versionCode")
            got_ios = expo.get("ios", {}).get("buildNumber")
            if got_android != want:
                errors.append(
                    f"android.versionCode {got_android} != expected {want} for {semver}"
                )
            if str(got_ios) != str(want):
                errors.append(
                    f"ios.buildNumber {got_ios} != expected {want} for {semver}"
                )

    if errors:
        print("\n".join(["✗ version check failed", *errors]), file=sys.stderr)
        return 1

    (semver,) = versions
    print(f"✓ version consistent: {semver} (versionCode {expected_version_code(semver)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
