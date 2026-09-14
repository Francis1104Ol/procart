from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unsupported_endpoint_returns_clear_error():
    response = client.get("/payments")

    assert response.status_code == 404

    body = response.json()

    assert body["error"] == "not_found"
    assert "not available" in body["message"]