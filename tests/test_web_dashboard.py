from pathlib import Path

from fastapi.testclient import TestClient

from ats.settings import settings
from ats.web.app import app
from ats.web.data import dashboard_snapshot


def test_dashboard_snapshot_missing_database(tmp_path: Path) -> None:
    snapshot = dashboard_snapshot(tmp_path / "missing.db")
    assert snapshot["database_ready"] is False
    assert snapshot["latest_decision"] is None


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_renders_without_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_path", tmp_path / "missing.db")
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "159558 每日决策台" in response.text
