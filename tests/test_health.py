from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_api_path_is_404_not_spa():
    assert client.get("/api/v1/does-not-exist").status_code == 404
