from app.config import Settings, get_settings


CONFIG_ENV_VARS = (
    "AI_PROVIDER",
    "REDIS_URL",
    "DATABASE_URL",
)

SARVAM_ENV_VARS = (
    "SARVAM_API_KEY",
    "SARVAM_API_BASE",
    "SARVAM_STT_MODEL",
    "SARVAM_STT_TRANSLATE_MODEL",
    "SARVAM_TRANSLATE_MODEL",
    "SARVAM_TTS_MODEL",
    "SARVAM_CHAT_MODEL",
    "SARVAM_TIMEOUT_SECONDS",
    "SARVAM_MAX_RETRIES",
    "SARVAM_FALLBACK_ON_ERROR",
    "ALLOW_PROVIDER_OVERRIDE",
)


ALL_SETTINGS_ENV_VARS = CONFIG_ENV_VARS + SARVAM_ENV_VARS


def clear_settings_env(monkeypatch):
    for env_var in ALL_SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_default_ai_provider_is_local(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.ai_provider == "local"


def test_get_settings_loads_settings_instance(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = get_settings()
    assert isinstance(settings, Settings)


def test_default_sarvam_settings(monkeypatch):
    clear_settings_env(monkeypatch)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.sarvam_api_key is None
    assert settings.sarvam_api_base == "https://api.sarvam.ai"
    assert settings.sarvam_stt_model == "saarika:v2.5"
    assert settings.sarvam_stt_translate_model == "saaras:v2.5"
    assert settings.sarvam_translate_model == "mayura:v1"
    assert settings.sarvam_tts_model == "bulbul:v3"
    assert settings.sarvam_chat_model == "sarvam-m"
    assert settings.sarvam_timeout_seconds == 30.0
    assert settings.sarvam_max_retries == 2
    assert settings.sarvam_fallback_on_error is True
    assert settings.allow_provider_override is False


def test_sarvam_settings_can_be_overridden_from_env(monkeypatch):
    clear_settings_env(monkeypatch)

    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    monkeypatch.setenv("SARVAM_API_BASE", "https://example.test")
    monkeypatch.setenv("SARVAM_STT_MODEL", "custom-stt")
    monkeypatch.setenv("SARVAM_STT_TRANSLATE_MODEL", "custom-stt-translate")
    monkeypatch.setenv("SARVAM_TRANSLATE_MODEL", "custom-translate")
    monkeypatch.setenv("SARVAM_TTS_MODEL", "custom-tts")
    monkeypatch.setenv("SARVAM_CHAT_MODEL", "custom-chat")
    monkeypatch.setenv("SARVAM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("SARVAM_MAX_RETRIES", "4")
    monkeypatch.setenv("SARVAM_FALLBACK_ON_ERROR", "false")
    monkeypatch.setenv("ALLOW_PROVIDER_OVERRIDE", "true")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.sarvam_api_key == "test-key"
    assert settings.sarvam_api_base == "https://example.test"
    assert settings.sarvam_stt_model == "custom-stt"
    assert settings.sarvam_stt_translate_model == "custom-stt-translate"
    assert settings.sarvam_translate_model == "custom-translate"
    assert settings.sarvam_tts_model == "custom-tts"
    assert settings.sarvam_chat_model == "custom-chat"
    assert settings.sarvam_timeout_seconds == 12.5
    assert settings.sarvam_max_retries == 4
    assert settings.sarvam_fallback_on_error is False
    assert settings.allow_provider_override is True
