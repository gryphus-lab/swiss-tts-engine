"""Bump the shared monorepo semantic version across all release surfaces."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from check_version import expected_version_code

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_FILE = "pyproject.toml"


def _next_version(version: str, level: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def _updated_toml(path: Path, old_version: str, new_version: str) -> str:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        rf'(?m)^(version\s*=\s*")({re.escape(old_version)})(")$',
        rf"\g<1>{new_version}\g<3>",
        content,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Could not uniquely update project version in {path}.")
    return updated


def _updated_json(
    path: Path,
    old_version: str,
    new_version: str,
    *,
    app_config: bool = False,
    lockfile: bool = False,
) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    if app_config:
        expo = data["expo"]
        if expo["version"] != old_version:
            raise ValueError(f"Unexpected version in {path}.")
        expo["version"] = new_version
        version_code = expected_version_code(new_version)
        expo["android"]["versionCode"] = version_code
        expo["ios"]["buildNumber"] = str(version_code)
    elif lockfile:
        if (
            data["version"] != old_version
            or data["packages"][""]["version"] != old_version
        ):
            raise ValueError(f"Unexpected version in {path}.")
        data["version"] = new_version
        data["packages"][""]["version"] = new_version
    else:
        if data["version"] != old_version:
            raise ValueError(f"Unexpected version in {path}.")
        data["version"] = new_version
    return json.dumps(data, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=("major", "minor", "patch"))
    level = parser.parse_args().level

    check = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_version.py")],
        cwd=ROOT,
        check=False,
    )
    if check.returncode:
        return check.returncode

    version = tomllib.loads((ROOT / PYPROJECT_FILE).read_text())["project"]["version"]
    new_version = _next_version(version, level)
    updates = {
        ROOT / PYPROJECT_FILE: _updated_toml(
            ROOT / PYPROJECT_FILE, version, new_version
        ),
        ROOT / "apps/swiss-tts-engine/pyproject.toml": _updated_toml(
            ROOT / "apps/swiss-tts-engine/pyproject.toml", version, new_version
        ),
        ROOT / "apps/swiss-tts-app/package.json": _updated_json(
            ROOT / "apps/swiss-tts-app/package.json", version, new_version
        ),
        ROOT / "apps/swiss-tts-app/package-lock.json": _updated_json(
            ROOT / "apps/swiss-tts-app/package-lock.json",
            version,
            new_version,
            lockfile=True,
        ),
        ROOT / "apps/swiss-tts-app/app.json": _updated_json(
            ROOT / "apps/swiss-tts-app/app.json",
            version,
            new_version,
            app_config=True,
        ),
    }
    for path, content in updates.items():
        path.write_text(content, encoding="utf-8")

    print(f"Bumped semantic version: {version} -> {new_version} ({level})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
