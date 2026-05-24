from typing import Any

from app.config import Settings
from app.services.ai_provider import (
    FallbackAIProvider,
    LocalAIProvider,
    SarvamAIProvider,
    CircuitBreaker,
    get_ai_provider,
)
from app.services.sarvam_client import SarvamError, SarvamTimeoutError


class FakePrimaryProvider:
    def __init__(self, failures=None):
        self.failures = list(failures or [])
        self.calls = []

    def transcribe_audio(self, audio_bytes, language_code="hi-IN", model=None):
        self.calls.append(("transcribe_audio", audio_bytes, language_code, model))
        if self.failures:
            raise self.failures.pop(0)
        from app.schemas import TranscriptionResult
        return TranscriptionResult(
            transcript="primary transcript",
            detected_language="hi-IN",
            confidence=0.9,
        )

    def translate_text(self, text, target_language, source_language=None):
        self.calls.append(("translate_text", text, target_language, source_language))
        if self.failures:
            raise self.failures.pop(0)
        return "primary translation"

    def extract_grievance(self, text, language="hi") -> Any:
        self.calls.append(("extract_grievance", text, language))
        if self.failures:
            raise self.failures.pop(0)
        return "primary extraction"

    def generate_draft(self, cluster_context):
        self.calls.append(("generate_draft", cluster_context))
        if self.failures:
            raise self.failures.pop(0)
        return "primary draft"


class FakeFallbackProvider:
    def __init__(self):
        self.calls = []

    def transcribe_audio(self, audio_bytes, language_code="hi-IN", model=None):
        self.calls.append(("transcribe_audio", audio_bytes, language_code, model))
        from app.schemas import TranscriptionResult
        return TranscriptionResult(
            transcript="fallback transcript",
            detected_language="hi-IN",
            confidence=0.0,
        )

    def translate_text(self, text, target_language, source_language=None):
        self.calls.append(("translate_text", text, target_language, source_language))
        return "fallback translation"

    def extract_grievance(self, text, language="hi") -> Any:
        self.calls.append(("extract_grievance", text, language))
        return "fallback extraction"

    def generate_draft(self, cluster_context):
        self.calls.append(("generate_draft", cluster_context))
        return "fallback draft"


def test_single_sarvam_error_falls_back_and_returns_fallback_result(caplog):
    primary = FakePrimaryProvider([SarvamTimeoutError("timeout")])
    fallback = FakeFallbackProvider()
    provider = FallbackAIProvider(primary, fallback)

    result = provider.translate_text("namaste", "en")

    assert result == "fallback translation"
    assert primary.calls == [("translate_text", "namaste", "en", None)]
    assert fallback.calls == [("translate_text", "namaste", "en", None)]
    assert "falling back to local AI provider" in caplog.text


def test_circuit_opens_after_threshold_and_skips_primary_until_recovery():
    now = [100.0]
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_seconds=30.0,
        time_func=lambda: now[0],
    )
    primary = FakePrimaryProvider([
        SarvamError("first"),
        SarvamError("second"),
    ])
    fallback = FakeFallbackProvider()
    provider = FallbackAIProvider(primary, fallback, circuit_breaker=breaker)

    assert provider.translate_text("one", "en") == "fallback translation"
    assert provider.translate_text("two", "en") == "fallback translation"
    assert len(primary.calls) == 2

    assert provider.translate_text("three", "en") == "fallback translation"

    assert len(primary.calls) == 2
    assert fallback.calls[-1] == ("translate_text", "three", "en", None)


def test_circuit_failure_count_resets_outside_failure_window():
    now = [100.0]
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_seconds=30.0,
        failure_window_seconds=10.0,
        time_func=lambda: now[0],
    )
    primary = FakePrimaryProvider([
        SarvamError("first"),
        SarvamError("second after window"),
    ])
    fallback = FakeFallbackProvider()
    provider = FallbackAIProvider(primary, fallback, circuit_breaker=breaker)

    assert provider.translate_text("one", "en") == "fallback translation"
    now[0] = 111.0
    assert provider.translate_text("two", "en") == "fallback translation"

    assert breaker.opened_at is None
    assert len(primary.calls) == 2
    assert provider.translate_text("three", "en") == "primary translation"
    assert len(primary.calls) == 3


def test_circuit_half_opens_after_timeout_and_resets_on_success():
    now = [100.0]
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=30.0,
        time_func=lambda: now[0],
    )
    primary = FakePrimaryProvider([SarvamError("first")])
    fallback = FakeFallbackProvider()
    provider = FallbackAIProvider(primary, fallback, circuit_breaker=breaker)

    assert provider.transcribe_audio(b"first").transcript == "fallback transcript"
    assert len(primary.calls) == 1

    assert provider.transcribe_audio(b"before-timeout").transcript == "fallback transcript"
    assert len(primary.calls) == 1

    now[0] = 131.0
    assert provider.transcribe_audio(b"after-timeout").transcript == "primary transcript"

    assert primary.calls[-1] == ("transcribe_audio", b"after-timeout", "hi-IN", None)
    assert provider.transcribe_audio(b"closed-again").transcript == "primary transcript"
    assert len(primary.calls) == 3


def test_get_ai_provider_reuses_circuit_breaker_across_request_scoped_instances(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="sarvam",
        sarvam_api_key="test-key",
        sarvam_fallback_on_error=True,
    )

    import app.services.ai_provider as ai_provider

    getattr(ai_provider, "_reset_sarvam_circuit_breaker_for_tests", lambda: None)()
    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)

    class AlwaysFailingSarvamProvider:
        calls = 0

        def translate_text(self, text, target_language, source_language=None):
            AlwaysFailingSarvamProvider.calls += 1
            raise SarvamError("sarvam unavailable")

    monkeypatch.setattr(ai_provider, "SarvamAIProvider", AlwaysFailingSarvamProvider)

    for index in range(3):
        provider = get_ai_provider()
        assert provider.translate_text("namaste-%s" % index, "en") == "namaste-%s" % index

    provider = get_ai_provider()
    assert provider.translate_text("skipped", "en") == "skipped"
    assert AlwaysFailingSarvamProvider.calls == 3


def test_get_ai_provider_wraps_sarvam_when_fallback_enabled(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="sarvam",
        sarvam_api_key="test-key",
        sarvam_fallback_on_error=True,
    )

    import app.services.ai_provider as ai_provider

    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)

    provider = get_ai_provider()

    assert isinstance(provider, FallbackAIProvider)
    assert isinstance(provider.primary, SarvamAIProvider)
    assert isinstance(provider.fallback, LocalAIProvider)


def test_get_ai_provider_uses_local_when_sarvam_init_fails_and_fallback_enabled(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="sarvam",
        sarvam_api_key=None,
        sarvam_fallback_on_error=True,
    )

    import app.services.ai_provider as ai_provider

    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)

    assert isinstance(get_ai_provider(), LocalAIProvider)


def test_get_ai_provider_returns_plain_sarvam_when_fallback_disabled(monkeypatch):
    settings = Settings(
        _env_file=None,
        ai_provider="sarvam",
        sarvam_api_key="test-key",
        sarvam_fallback_on_error=False,
    )

    import app.services.ai_provider as ai_provider

    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)

    assert isinstance(get_ai_provider(), SarvamAIProvider)
