import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from src.app import app


def test_health_returns_healthy_status():
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_unknown_route_returns_404_with_correlation_id():
    response = app.test_client().get(
        "/missing",
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Not Found"
    assert response.get_json()["correlationId"] == "test-correlation-id"


def test_method_not_allowed_preserves_405_status():
    response = app.test_client().post("/health")

    assert response.status_code == 405
    assert response.get_json()["error"] == "Method Not Allowed"


def test_controlled_validation_error_uses_400_label():
    response = app.test_client().post(
        "/api/exceptions/test-error",
        json={"errorType": "validation"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Bad Request"
