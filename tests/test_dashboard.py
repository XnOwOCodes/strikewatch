from fastapi.testclient import TestClient

from strikewatch.cycle import run_cycle
from strikewatch.dashboard import create_app


def test_health_and_empty_status(tmp_settings):
    client = TestClient(create_app(tmp_settings))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["decision"] == "none"
    page = client.get("/")
    assert page.status_code == 200
    assert "StrikeWatch" in page.text
    assert "textarea" not in page.text.lower()
    lowered = page.text.lower()
    assert "chatbot" in lowered or "not a chat" in lowered


def test_dashboard_shows_alert(fat_settings):
    run_cycle(fat_settings)
    client = TestClient(create_app(fat_settings))
    page = client.get("/")
    assert "ALERT" in page.text
    status = client.get("/api/status")
    assert status.json()["decision"] == "alert"


def test_post_api_cycle_quiet(tmp_settings):
    client = TestClient(create_app(tmp_settings))
    response = client.post("/api/cycle")
    assert response.status_code == 200
    assert response.json()["decision"] == "quiet"
