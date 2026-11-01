#!/usr/bin/env python3
"""Verify the semantic version is identical across every version surface.

The monorepo keeps one semantic version (see /VERSIONING.md). It is written in
several files; this script fails (exit 1) if any of them disagree, so drift is
caught in CI instead of shipping mismatched artifacts.

Surfaces checked:
  - pyproject.toml                              (monorepo)
  - apps/swiss-tts-engine/pyproject.toml        (engine package -> FastAPI version)
  - apps/swiss-tts-app/package.json             (Expo app, npm)
  - apps/swiss-tts-app/package-lock.json        (npm lockfile)
  - apps/swiss-tts-app/app.json                 (Expo app; also versionCode/buildNumber)

Run:  uv run python scripts/check_version.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOT_PYPROJECT_PATH = "pyproject.toml"
ENGINE_PYPROJECT_PATH = "apps/swiss-tts-engine/pyproject.toml"
APP_PACKAGE_PATH = "apps/swiss-tts-app/package.json"
APP_PACKAGE_LOCK_PATH = "apps/swiss-tts-app/package-lock.json"
APP_JSON_PATH = "apps/swiss-tts-app/app.json"

VERSION_PATHS = (
    ROOT_PYPROJECT_PATH,
    ENGINE_PYPROJECT_PATH,
    APP_PACKAGE_PATH,
    APP_PACKAGE_LOCK_PATH,
    APP_JSON_PATH,
)


def _toml_version(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode()
    return tomllib.loads(content.decode())["project"]["version"]


def _json_version(content: str | bytes, *keys: str) -> str:
    if isinstance(content, bytes):
        content = content.decode()
    data = json.loads(content)
    for key in keys:
        data = data[key]
    return data


def _surface_versions(root: Path) -> dict[str, str]:
    package_lock = (root / APP_PACKAGE_LOCK_PATH).read_bytes()
    return {
        ROOT_PYPROJECT_PATH: _toml_version(
            (root / ROOT_PYPROJECT_PATH).read_bytes()
        ),
        ENGINE_PYPROJECT_PATH: _toml_version(
            (root / ENGINE_PYPROJECT_PATH).read_bytes()
        ),
        APP_PACKAGE_PATH: _json_version(
            (root / APP_PACKAGE_PATH).read_bytes(), "version"
        ),
        APP_PACKAGE_LOCK_PATH: _json_version(package_lock, "version"),
        f'{APP_PACKAGE_LOCK_PATH} packages[""]': _json_version(
            package_lock,
            "packages",
            "",
            "version",
        ),
        APP_JSON_PATH: _json_version(
            (root / APP_JSON_PATH).read_bytes(), "expo", "version"
        ),
    }


def _read_ref_file(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"Cannot read {path} from '{ref}'. Fetch the ref and retry.")
    return result.stdout


def _surface_versions_from_ref(ref: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for path in VERSION_PATHS:
        content = _read_ref_file(ref, path)
        if path.endswith(".toml"):
            versions[path] = _toml_version(content)
        elif path in (APP_PACKAGE_PATH, APP_PACKAGE_LOCK_PATH):
            versions[path] = _json_version(content, "version")
            if path == APP_PACKAGE_LOCK_PATH:
                versions[f'{path} packages[""]'] = _json_version(
                    content, "packages", "", "version"
                )
        else:
            versions[path] = _json_version(content, "expo", "version")
    return versions


def expected_version_code(semver: str) -> int:
    """MAJOR*1_000_000 + MINOR*10_000 + PATCH (monotonic, lots of patch room)."""
    major, minor, patch = (int(p) for p in semver.split("."))
    return major * 1_000_000 + minor * 10_000 + patch


def _validate_version(
    surfaces: dict[str, str], app_json: dict[str, object]
) -> list[str]:
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
            expo = app_json["expo"]
            assert isinstance(expo, dict)
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

    return errors


def _version_from_ref(ref: str) -> str:
    versions = _surface_versions_from_ref(ref)
    if len(set(versions.values())) != 1:
        raise ValueError(f"Version surfaces in '{ref}' are inconsistent: {versions}")
    version = next(iter(versions.values()))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Version '{version}' in '{ref}' is not MAJOR.MINOR.PATCH.")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--against-ref",
        help="Require the checked version to be greater than this Git ref's version",
    )
    parser.add_argument(
        "--from-ref",
        help="Check version files from this Git ref instead of the working tree",
    )
    args = parser.parse_args()

    if args.from_ref:
        surfaces = _surface_versions_from_ref(args.from_ref)
        app_json = json.loads(_read_ref_file(args.from_ref, VERSION_PATHS[-1]))
    else:
        surfaces = _surface_versions(ROOT)
        app_json = json.loads(
            (ROOT / APP_JSON_PATH).read_text(encoding="utf-8")
        )
    errors = _validate_version(surfaces, app_json)
    semver = (
        next(iter(set(surfaces.values()))) if len(set(surfaces.values())) == 1 else None
    )
    if args.against_ref:
        try:
            reference_version = _version_from_ref(args.against_ref)
            if (
                semver
                and re.fullmatch(r"\d+\.\d+\.\d+", semver)
                and tuple(map(int, semver.split(".")))
                <= tuple(map(int, reference_version.split(".")))
            ):
                errors.append(
                    f"Version {semver} must be greater than "
                    f"{reference_version} in '{args.against_ref}'."
                )
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        print("\n".join(["✗ version check failed", *errors]), file=sys.stderr)
        return 1

    assert semver is not None
    print(
        f"✓ version consistent: {semver} (versionCode {expected_version_code(semver)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
