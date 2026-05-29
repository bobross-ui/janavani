from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_expo_ios_post_json():
    """WKWebView preflight that caused the original join-cluster bug."""
    client = TestClient(app)
    response = client.options(
        "/clusters/fake-id/support",
        headers={
            "Origin": "http://192.168.29.73:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_cors_preflight_expo_ios_get():
    """Simple GET from Expo origin should also pass."""
    client = TestClient(app)
    response = client.options(
        "/clusters",
        headers={
            "Origin": "http://192.168.29.73:8081",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"