from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_configured_origin_passes_cors_preflight() -> None:
    origin = app.user_middleware[0].kwargs["allow_origins"][0]

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/resume/analyze",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_history_preflight_does_not_require_auth() -> None:
    origin = app.user_middleware[0].kwargs["allow_origins"][0]

    with TestClient(app) as client:
        list_response = client.options(
            "/api/v1/resume/analyses",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        read_response = client.options(
            "/api/v1/resume/analyses/00000000-0000-0000-0000-0000000000aa",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert list_response.status_code == 200
    assert read_response.status_code == 200
    assert list_response.headers["access-control-allow-origin"] == origin
    assert read_response.headers["access-control-allow-origin"] == origin


def test_unknown_origin_is_not_allowed() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/resume/analyze",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert "access-control-allow-origin" not in response.headers
