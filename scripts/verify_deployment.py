#!/usr/bin/env python3
"""Verify deployment readiness for CareerOS."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQUIRED_BACKEND_VARS = [
    "DATABASE_URL",
    "SECRET_KEY",
    "ANTHROPIC_API_KEY",
    "ALLOWED_ORIGINS",
    "ENVIRONMENT",
]

REQUIRED_FRONTEND_ARTIFACTS = [
    ROOT / "frontend" / "build" / "index.html",
    ROOT / "frontend" / "build" / "assets",
    ROOT / "frontend" / "vercel.json",
    ROOT / "frontend" / "package.json",
    ROOT / "render.yaml",
    ROOT / "requirements-prod.txt",
]


def check_backend_import() -> list[str]:
    errors: list[str] = []
    try:
        importlib.import_module("app.main")
    except Exception as exc:
        errors.append(f"Backend import failed: {exc}")
    return errors


def check_env_vars() -> list[str]:
    missing = [name for name in REQUIRED_BACKEND_VARS if not os.getenv(name)]
    if missing:
        return [f"Missing environment variables: {', '.join(missing)}"]
    return []


def check_frontend_artifacts() -> list[str]:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_FRONTEND_ARTIFACTS if not path.exists()]
    if missing:
        return [f"Missing frontend/deployment artifacts: {', '.join(missing)}"]
    return []

def check_deployment_config() -> list[str]:
    errors: list[str] = []
    vercel_config = json.loads(
        (ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8")
    )
    if vercel_config.get("outputDirectory") != "build":
        errors.append("Vercel outputDirectory must be build")

    render_config = (ROOT / "render.yaml").read_text(encoding="utf-8")
    required_render_values = [
        "preDeployCommand: alembic upgrade head",
        "startCommand: bash scripts/start.sh",
        "healthCheckPath: /health",
    ]
    for value in required_render_values:
        if value not in render_config:
            errors.append(f"render.yaml is missing: {value}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(check_frontend_artifacts())
    errors.extend(check_deployment_config())
    errors.extend(check_env_vars())
    errors.extend(check_backend_import())

    if errors:
        print("DEPLOYMENT CHECK: FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("DEPLOYMENT CHECK: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
