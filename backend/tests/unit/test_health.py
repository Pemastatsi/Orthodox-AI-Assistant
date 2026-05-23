"""Smoke test: /health returns 200 with the documented shape."""

from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_emits_run_id_header() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert "x-run-id" in {k.lower() for k in response.headers}
