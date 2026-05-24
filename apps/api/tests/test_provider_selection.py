import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import get_session
from app.main import app
from app.services.ai_provider import FallbackAIProvider, LocalAIProvider, SarvamAIProvider


def isolated_settings(**overrides):
    values = {
        "ai_provider": "local",
        "allow_provider_override": False,
        "sarvam_api_key": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def patch_settings(monkeypatch, **overrides):
    settings = isolated_settings(**overrides)

    import app.routes.grievances as grievances
    import app.services.ai_provider as ai_provider

    monkeypatch.setattr(grievances, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)
    return settings


def test_default_request_provider_is_local(monkeypatch):
    patch_settings(monkeypatch)

    from app.routes.grievances import get_request_ai_provider

    assert isinstance(get_request_ai_provider(), LocalAIProvider)


def test_provider_selection_reads_current_settings_without_route_reimport(monkeypatch):
    from app.routes.grievances import get_request_ai_provider

    patch_settings(monkeypatch, ai_provider="local")
    assert isinstance(get_request_ai_provider(), LocalAIProvider)

    patch_settings(
        monkeypatch,
        ai_provider="sarvam",
        sarvam_api_key="test-key",
    )
    provider = get_request_ai_provider()
    assert isinstance(provider, FallbackAIProvider)
    assert isinstance(provider.primary, SarvamAIProvider)
    assert isinstance(provider.fallback, LocalAIProvider)


def test_provider_override_header_is_ignored_when_not_allowed(monkeypatch):
    patch_settings(
        monkeypatch,
        ai_provider="local",
        allow_provider_override=False,
    )

    from app.routes.grievances import get_request_ai_provider

    assert isinstance(
        get_request_ai_provider(x_ai_provider="sarvam"), LocalAIProvider
    )


def test_provider_override_unknown_header_is_ignored_when_not_allowed(monkeypatch):
    patch_settings(
        monkeypatch,
        ai_provider="local",
        allow_provider_override=False,
    )

    from app.routes.grievances import get_request_ai_provider

    assert isinstance(
        get_request_ai_provider(x_ai_provider="bhasha-test"), LocalAIProvider
    )


def test_provider_override_header_is_honored_when_allowed(monkeypatch):
    patch_settings(
        monkeypatch,
        ai_provider="sarvam",
        allow_provider_override=True,
        sarvam_api_key="test-key",
    )

    from app.routes.grievances import get_request_ai_provider

    assert isinstance(
        get_request_ai_provider(x_ai_provider="local"), LocalAIProvider
    )


def test_provider_override_rejects_unknown_provider_when_allowed(monkeypatch):
    patch_settings(monkeypatch, allow_provider_override=True)

    from app.routes.grievances import get_request_ai_provider

    with pytest.raises(HTTPException, match="Unsupported AI provider override") as exc:
        get_request_ai_provider(x_ai_provider="bhasha-test")
    assert exc.value.status_code == 400


def test_provider_override_rejects_unavailable_sarvam_when_allowed(monkeypatch):
    patch_settings(
        monkeypatch,
        ai_provider="local",
        allow_provider_override=True,
        sarvam_api_key="test-key",
    )

    from app.routes.grievances import get_request_ai_provider

    with pytest.raises(HTTPException, match="Sarvam provider override is not available yet") as exc:
        get_request_ai_provider(x_ai_provider="sarvam")
    assert exc.value.status_code == 503


def test_client_header_alias_returns_controlled_error_for_unavailable_sarvam(monkeypatch):
    patch_settings(
        monkeypatch,
        ai_provider="local",
        allow_provider_override=True,
        sarvam_api_key="test-key",
    )

    session_requested = False

    def fail_if_session_requested():
        nonlocal session_requested
        session_requested = True
        raise AssertionError("DB session should not be requested for unavailable provider override")
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = fail_if_session_requested
    try:
        client = TestClient(app)
        response = client.post(
            "/grievances",
            headers={"X-AI-Provider": "sarvam"},
            json={
                "user_id": "test-user",
                "text": "ward 8 mein paani nahi aa raha",
                "language": "hi-Latn",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Sarvam provider override is not available yet"
    }
    assert session_requested is False


def test_client_unsupported_override_ignored_when_override_disabled(monkeypatch):
    patch_settings(
        monkeypatch,
        ai_provider="local",
        allow_provider_override=False,
    )

    from app.routes.grievances import get_request_ai_provider

    assert isinstance(
        get_request_ai_provider(x_ai_provider="bhasha-test"), LocalAIProvider
    )
