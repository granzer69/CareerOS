from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.core.startup import initialize_database
from app.main import app


def test_health_reports_database_and_missing_local_model() -> None:
    """Health stays up without GGUF weights and reports local_model=missing."""
    asyncio.run(initialize_database())
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["local_model"] == "missing"
    assert "llama" not in response.text.lower()
