from app.config import get_settings


def test_default_ai_provider_is_local():
    settings = get_settings()
    assert settings.ai_provider == "local"
