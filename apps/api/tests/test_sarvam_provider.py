"""Tests for SarvamAIProvider.generate_draft — all mocked, no real HTTP."""

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.services.ai_provider import SarvamAIProvider
from app.services.sarvam_client import SarvamError


# ── Fake / Mock helpers ───────────────────────────────────────────────


class FakeSarvamClient:
    """Drop-in fake that records calls and returns configured responses."""

    def __init__(self, response: Optional[Dict[str, Any]] = None):
        self._response = response or {}
        self.calls: list = []

    def post_json(self, path: str, payload: dict) -> dict:
        self.calls.append((path, payload))
        return self._response

    def post_audio_bytes(
        self, path: str, audio_bytes: bytes, model: str, language: Optional[str]
    ) -> dict:
        self.calls.append((path, audio_bytes, model, language))
        return self._response

    def close(self) -> None:
        pass


def _chat_response(content: str) -> Dict[str, Any]:
    """Return an OpenAI‑compatible chat completion response."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


def _cluster_context(**overrides) -> dict:
    """Return a minimal realistic cluster_context dict."""
    defaults = {
        "title": "Jal Aapurti Samasya",
        "department": "jal_board",
        "area": "Ward 8",
        "language": "hi",
        "ward": "8",
        "grievance_count": 12,
        "summary": "Pichle 4 dino se pani nahi aa raha.",
        "sample_grievances": [
            {"id": "g1", "pii_redacted_text": "Ward 8 me pani nahi aa raha hai."},
            {"id": "g2", "pii_redacted_text": "4 din se jal aapurti band hai."},
            {
                "id": "g3",
                "pii_redacted_text": "Ward 8 ki jal aapurti mein samasya.",
            },
            {"id": "g4", "pii_redacted_text": "Pani ki kami se parivarik jeevan prabhavit."},
            {"id": "g5", "pii_redacted_text": "4 din se pani ki ek boond nahi."},
            {"id": "g6", "pii_redacted_text": "Jal board ko soochit kiya par koi karwai nahi."},
        ],
    }
    defaults.update(overrides)
    return defaults


# ── Tests ─────────────────────────────────────────────────────────────


class TestGenerateDraft:
    """All generate_draft tests use FakeSarvamClient — zero HTTP."""

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_provider(
        mock_response: Optional[Dict[str, Any]] = None,
        settings_overrides: Optional[Dict[str, Any]] = None,
    ) -> SarvamAIProvider:
        """Build a SarvamAIProvider wired to a FakeSarvamClient.

        Also monkeypatches get_settings() so the provider picks up any
        overrides *and* has a valid api_key so __init__ succeeds.
        """
        import app.services.ai_provider as mod

        overrides = dict(settings_overrides or {})
        overrides.setdefault("sarvam_api_key", "fake-key-for-tests")
        overrides.setdefault("sarvam_chat_model", "sarvam-m")
        overrides.setdefault("sarvam_api_base", "https://api.sarvam.ai")
        overrides.setdefault("sarvam_timeout_seconds", 30.0)
        overrides.setdefault("sarvam_max_retries", 0)

        test_settings = Settings(_env_file=None, **overrides)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mod, "get_settings", lambda: test_settings)

        fake_client = FakeSarvamClient(response=mock_response)
        try:
            return SarvamAIProvider(client=fake_client)
        finally:
            monkeypatch.undo()

    # ── happy path ──────────────────────────────────────────────

    def test_generate_draft_returns_string_with_department_ward_count(self):
        draft_text = (
            "To,\nThe Jal Board,\n\n"
            "Subject: Jal Aapurti Samasya — Ward 8\n\n"
            "Respected Sir/Madam,\n\n"
            "We, the undersigned 12 citizens of Ward 8, wish to bring "
            "the following issue to your attention..."
        )
        provider = self._make_provider(
            mock_response=_chat_response(draft_text),
        )
        ctx = _cluster_context()
        result = provider.generate_draft(ctx)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Jal Board" in result
        assert "Ward 8" in result
        assert "12" in result

    # ── PII guard ───────────────────────────────────────────────

    def test_generate_draft_rejects_10_digit_number(self):
        """10-digit phone patterns in generated draft → SarvamError."""
        leaky = "Call me at 9876543210 for more details. — Ward 8"
        provider = self._make_provider(
            mock_response=_chat_response(leaky),
        )
        with pytest.raises(SarvamError, match="PII"):
            provider.generate_draft(_cluster_context())

    def test_generate_draft_rejects_email_address(self):
        """Email in generated draft → SarvamError."""
        leaky = "Email test@example.com for details."
        provider = self._make_provider(
            mock_response=_chat_response(leaky),
        )
        with pytest.raises(SarvamError, match="PII"):
            provider.generate_draft(_cluster_context())

    def test_generate_draft_allows_9_digit_number(self):
        """9-digit strings are NOT treated as phone leaks."""
        safe = "The road is 123456789 meters long."
        provider = self._make_provider(
            mock_response=_chat_response(safe),
        )
        result = provider.generate_draft(_cluster_context())
        assert "123456789" in result  # no PII error raised

    def test_generate_draft_allows_10_digits_inside_longer_number(self):
        """10 digits inside a longer string are not a standalone phone number."""
        safe = "Reference ID: REF98765432109 should be fine."
        provider = self._make_provider(
            mock_response=_chat_response(safe),
        )
        result = provider.generate_draft(_cluster_context())
        assert "REF98765432109" in result  # 12 chars, no PII error

    # ── response extraction ─────────────────────────────────────

    def test_generate_draft_extracts_message_from_chat_response(self):
        expected = "To,\nThe Jal Board,\n\nSubject: Water Crisis\n\n..."
        provider = self._make_provider(
            mock_response=_chat_response(expected),
        )
        result = provider.generate_draft(_cluster_context())
        assert result == expected

    def test_generate_draft_rejects_empty_choices(self):
        provider = self._make_provider(
            mock_response={"choices": []},
        )
        with pytest.raises(SarvamError, match="response shape"):
            provider.generate_draft(_cluster_context())

    def test_generate_draft_rejects_missing_message_key(self):
        provider = self._make_provider(
            mock_response={"choices": [{"no_message": 1}]},
        )
        with pytest.raises(SarvamError, match="response shape"):
            provider.generate_draft(_cluster_context())

    def test_generate_draft_rejects_null_content(self):
        provider = self._make_provider(
            mock_response={"choices": [{"message": {"content": None}}]},
        )
        with pytest.raises(SarvamError, match="not a string"):
            provider.generate_draft(_cluster_context())

    def test_generate_draft_rejects_empty_content(self):
        provider = self._make_provider(
            mock_response={"choices": [{"message": {"content": "   "}}]},
        )
        with pytest.raises(SarvamError, match="empty"):
            provider.generate_draft(_cluster_context())

    # ── payload verification ────────────────────────────────────

    def test_generate_draft_uses_temperature_0_2(self):
        provider = self._make_provider(
            mock_response=_chat_response("draft"),
        )
        provider.generate_draft(_cluster_context())

        # Inspect captured call
        fake = provider.client  # our FakeSarvamClient
        assert len(fake.calls) == 1
        path, payload = fake.calls[0]
        assert path == "/v1/chat/completions"
        assert payload["temperature"] == 0.2

    def test_generate_draft_uses_configured_chat_model(self):
        provider = self._make_provider(
            mock_response=_chat_response("draft"),
            settings_overrides={"sarvam_chat_model": "sarvam-m"},
        )
        provider.generate_draft(_cluster_context())

        fake = provider.client
        _, payload = fake.calls[0]
        assert payload["model"] == "sarvam-m"

    # ── prompt construction ─────────────────────────────────────

    def test_generate_draft_builds_system_prompt_with_language_and_department(self):
        provider = self._make_provider(
            mock_response=_chat_response("draft"),
            settings_overrides={"sarvam_chat_model": "sarvam-m"},
        )
        ctx = _cluster_context(language="hi", department="jal_board")
        provider.generate_draft(ctx)

        fake = provider.client
        _, payload = fake.calls[0]
        messages = payload["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "hi" in system_msg["content"] or "Hindi" in system_msg["content"]
        assert "jal_board" in system_msg["content"]

    def test_generate_draft_passes_only_redacted_samples(self):
        """User prompt should reference pii_redacted_text, never raw_text."""
        provider = self._make_provider(
            mock_response=_chat_response("draft"),
        )
        ctx = _cluster_context(
            sample_grievances=[
                {
                    "id": "g1",
                    "raw_text": "Mera number 9876543210 hai pani nahi aa raha",
                    "pii_redacted_text": "Mera number [PHONE_REDACTED] hai pani nahi aa raha",
                },
                {
                    "id": "g2",
                    "raw_text": "Email test@x.com pe sampark karein",
                    "pii_redacted_text": "Email [EMAIL_REDACTED] pe sampark karein",
                },
            ]
        )
        provider.generate_draft(ctx)

        fake = provider.client
        _, payload = fake.calls[0]
        user_msg_content = next(
            m["content"] for m in payload["messages"] if m["role"] == "user"
        )

        # Must include redacted versions
        assert "[PHONE_REDACTED]" in user_msg_content
        assert "[EMAIL_REDACTED]" in user_msg_content
        # Must NOT include raw PII
        assert "9876543210" not in user_msg_content
        assert "test@x.com" not in user_msg_content

    # ── privacy: no logging of generated draft ──────────────────

    def test_generate_draft_does_not_log_generated_text(self, caplog):
        import logging

        draft = "This is a sensitive draft about Ward 8."
        provider = self._make_provider(
            mock_response=_chat_response(draft),
        )
        with caplog.at_level(logging.DEBUG):
            provider.generate_draft(_cluster_context())

        # The generated text must never appear in logs
        assert draft not in caplog.text


# ── Translate response helper ────────────────────────────────────────


def _translate_response(translated_text: str) -> Dict[str, Any]:
    """Return a Sarvam Mayura translate response shape."""
    return {"translated_text": translated_text}


# ── Translate tests ──────────────────────────────────────────────────


class TestTranslateText:
    """All translate_text tests use FakeSarvamClient — zero HTTP."""

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_provider(
        mock_response: Optional[Dict[str, Any]] = None,
        settings_overrides: Optional[Dict[str, Any]] = None,
    ) -> SarvamAIProvider:
        """Build a SarvamAIProvider wired to a FakeSarvamClient."""
        import app.services.ai_provider as mod

        overrides = dict(settings_overrides or {})
        overrides.setdefault("sarvam_api_key", "fake-key-for-tests")
        overrides.setdefault("sarvam_translate_model", "mayura:v1")
        overrides.setdefault("sarvam_api_base", "https://api.sarvam.ai")
        overrides.setdefault("sarvam_timeout_seconds", 30.0)
        overrides.setdefault("sarvam_max_retries", 0)

        test_settings = Settings(_env_file=None, **overrides)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mod, "get_settings", lambda: test_settings)

        fake_client = FakeSarvamClient(response=mock_response)
        try:
            provider = SarvamAIProvider(client=fake_client)
            # Reset cache between tests
            provider._translate_cache = {}
            return provider
        finally:
            monkeypatch.undo()

    # ── happy path ──────────────────────────────────────────────

    def test_translate_text_returns_translation(self):
        """Mock client returns translated_text; verify result."""
        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        result = provider.translate_text("नमस्ते", "en", source_language="hi")
        assert result == "Hello"

    # ── skip when source == target ──────────────────────────────

    def test_translate_text_skips_when_source_equals_target(self):
        """source==target → no API call, returns text unchanged."""
        provider = self._make_provider(
            mock_response=_translate_response("should not be called"),
        )
        result = provider.translate_text("नमस्ते", "hi", source_language="hi")
        assert result == "नमस्ते"
        # Must not have made any API call
        fake = provider.client
        assert len(fake.calls) == 0

    # ── payload verification ────────────────────────────────────

    def test_translate_text_calls_translate_endpoint_with_correct_payload(self):
        """Verify /translate path, model, input, target fields."""
        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        provider.translate_text("नमस्ते", "en", source_language="hi")

        fake = provider.client
        assert len(fake.calls) == 1
        path, payload = fake.calls[0]
        assert path == "/translate"
        assert payload["model"] == "mayura:v1"
        assert payload["input"] == "नमस्ते"
        assert payload["target_language_code"] == "en"

    def test_translate_text_includes_source_when_provided(self):
        """Verify source_language_code in payload when provided."""
        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        provider.translate_text("नमस्ते", "en", source_language="hi")

        fake = provider.client
        _, payload = fake.calls[0]
        assert payload["source_language_code"] == "hi"

    def test_translate_text_auto_detects_source_when_omitted(self):
        """When source_language not provided, it is absent from payload."""
        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        provider.translate_text("नमस्ते", "en")

        fake = provider.client
        _, payload = fake.calls[0]
        assert "source_language_code" not in payload

    # ── response extraction ─────────────────────────────────────

    def test_translate_text_extracts_translated_text_field(self):
        """Verify response field extraction from translated_text key."""
        provider = self._make_provider(
            mock_response={"translated_text": "Bonjour"},
        )
        result = provider.translate_text("Hello", "fr", source_language="en")
        assert result == "Bonjour"

    def test_translate_text_handles_missing_translated_text_key(self):
        """Response without translated_text key → SarvamError."""
        provider = self._make_provider(
            mock_response={"some_other_key": "value"},
        )
        with pytest.raises(SarvamError, match="translated_text"):
            provider.translate_text("Hello", "fr", source_language="en")

    # ── caching ─────────────────────────────────────────────────

    def test_translate_text_caches_identical_request(self):
        """Two calls with same text+target → only one API call."""
        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        result1 = provider.translate_text("नमस्ते", "en", source_language="hi")
        result2 = provider.translate_text("नमस्ते", "en", source_language="hi")

        assert result1 == "Hello"
        assert result2 == "Hello"
        fake = provider.client
        assert len(fake.calls) == 1

    def test_translate_text_cache_key_includes_source_language(self):
        """Same text+target but different source → separate API calls."""
        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        provider.translate_text("नमस्ते", "en", source_language="hi")
        provider.translate_text("नमस्ते", "en", source_language="mr")

        fake = provider.client
        assert len(fake.calls) == 2

    def test_translate_text_rejects_null_translated_text(self):
        """Null translated_text → SarvamError."""
        provider = self._make_provider(
            mock_response={"translated_text": None},
        )
        with pytest.raises(SarvamError, match="not a string"):
            provider.translate_text("Hello", "fr", source_language="en")

    def test_translate_text_rejects_empty_translated_text(self):
        """Whitespace-only translated_text → SarvamError."""
        provider = self._make_provider(
            mock_response={"translated_text": "   "},
        )
        with pytest.raises(SarvamError, match="empty"):
            provider.translate_text("Hello", "fr", source_language="en")

    # ── privacy: no logging of text content ─────────────────────

    def test_translate_text_does_not_log_text_or_translation(self, caplog):
        """Neither the input text nor the translated text may appear in logs."""
        import logging

        provider = self._make_provider(
            mock_response=_translate_response("Hello"),
        )
        with caplog.at_level(logging.DEBUG):
            provider.translate_text("नमस्ते", "en", source_language="hi")

        assert "नमस्ते" not in caplog.text
        assert "Hello" not in caplog.text


# ── STT response helper ──────────────────────────────────────────────


def _stt_response(
    transcript: str = "ward 8 mein paani nahi aa raha",
    language_code: str = "hi-IN",
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Return a Sarvam speech-to-text response shape."""
    return {
        "transcript": transcript,
        "language_code": language_code,
        "confidence": confidence,
    }


# ── TranscribeAudio tests ────────────────────────────────────────────


class TestTranscribeAudio:
    """All transcribe_audio tests use FakeSarvamClient — zero HTTP."""

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_provider(
        mock_response: Optional[Dict[str, Any]] = None,
        settings_overrides: Optional[Dict[str, Any]] = None,
    ) -> SarvamAIProvider:
        """Build a SarvamAIProvider wired to a FakeSarvamClient.

        Keeps the monkeypatch active so get_settings() returns the
        test settings for the lifetime of the provider.
        """
        import app.services.ai_provider as mod

        overrides = dict(settings_overrides or {})
        overrides.setdefault("sarvam_api_key", "fake-key-for-tests")
        overrides.setdefault("sarvam_stt_model", "saarika:v2.5")
        overrides.setdefault("sarvam_api_base", "https://api.sarvam.ai")
        overrides.setdefault("sarvam_timeout_seconds", 30.0)
        overrides.setdefault("sarvam_max_retries", 0)

        test_settings = Settings(_env_file=None, **overrides)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mod, "get_settings", lambda: test_settings)

        fake_client = FakeSarvamClient(response=mock_response)
        provider = SarvamAIProvider(client=fake_client)
        # attach monkeypatch to provider so it stays alive
        provider._test_monkeypatch = monkeypatch  # type: ignore[attr-defined]
        return provider

    # ── happy path ──────────────────────────────────────────────

    def test_transcribe_audio_returns_transcription_result(self):
        """Happy path: returns TranscriptionResult with correct fields."""
        provider = self._make_provider(
            mock_response=_stt_response(
                transcript="ward 8 mein paani nahi aa raha",
                language_code="hi-IN",
                confidence=0.95,
            ),
        )
        result = provider.transcribe_audio(b"fake wav audio")

        assert result.transcript == "ward 8 mein paani nahi aa raha"
        assert result.detected_language == "hi-IN"
        assert result.confidence == 0.95
        assert isinstance(result.confidence, float)

    def test_transcribe_audio_calls_stt_endpoint_with_correct_params(self):
        """Verify /speech-to-text path, model, language, audio_bytes."""
        provider = self._make_provider(
            mock_response=_stt_response(),
        )
        audio = b"dummy audio content"
        provider.transcribe_audio(audio, language_code="hi-IN")

        fake = provider.client
        assert len(fake.calls) == 1
        call = fake.calls[0]
        # call format: (path, audio_bytes, model, language)
        assert call[0] == "/speech-to-text"
        assert call[1] == audio
        assert call[2] == "saarika:v2.5"
        assert call[3] == "hi-IN"

    # ── defaults ────────────────────────────────────────────────

    def test_transcribe_audio_uses_default_language(self):
        """Default language_code is 'hi-IN' when not provided."""
        provider = self._make_provider(
            mock_response=_stt_response(),
        )
        provider.transcribe_audio(b"audio")

        fake = provider.client
        _, _, model, language = fake.calls[0]
        assert language == "hi-IN"

    def test_transcribe_audio_uses_configured_model(self):
        """Uses sarvam_stt_model from settings when model is not provided."""
        provider = self._make_provider(
            mock_response=_stt_response(),
            settings_overrides={"sarvam_stt_model": "saaras:v2.5"},
        )
        provider.transcribe_audio(b"audio")

        fake = provider.client
        _, _, model, _ = fake.calls[0]
        assert model == "saaras:v2.5"

    def test_transcribe_audio_uses_explicit_model_over_settings(self):
        """Explicit model parameter overrides settings."""
        provider = self._make_provider(
            mock_response=_stt_response(),
            settings_overrides={"sarvam_stt_model": "saarika:v2.5"},
        )
        provider.transcribe_audio(b"audio", model="custom-stt-model")

        fake = provider.client
        _, _, model, _ = fake.calls[0]
        assert model == "custom-stt-model"

    # ── size validation ─────────────────────────────────────────

    def test_transcribe_audio_rejects_audio_over_10mb(self):
        """Audio > 10 MB raises SarvamError before any API call."""
        provider = self._make_provider(
            mock_response=_stt_response(),
        )
        large_audio = b"x" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte

        with pytest.raises(SarvamError, match="10"):
            provider.transcribe_audio(large_audio)

        # Must not have made any API call
        fake = provider.client
        assert len(fake.calls) == 0

    def test_transcribe_audio_accepts_audio_at_10mb(self):
        """Audio exactly at 10 MB is accepted."""
        provider = self._make_provider(
            mock_response=_stt_response(),
        )
        exact_audio = b"x" * (10 * 1024 * 1024)  # exactly 10 MB

        result = provider.transcribe_audio(exact_audio)
        assert result.transcript == "ward 8 mein paani nahi aa raha"
        assert len(provider.client.calls) == 1

    # ── response extraction ─────────────────────────────────────

    def test_transcribe_audio_missing_transcript_key(self):
        """Response without 'transcript' key → SarvamError."""
        provider = self._make_provider(
            mock_response={"language_code": "hi-IN", "confidence": 0.9},
        )
        with pytest.raises(SarvamError, match="transcript"):
            provider.transcribe_audio(b"audio")

    def test_transcribe_audio_rejects_null_transcript(self):
        """Null transcript → SarvamError."""
        provider = self._make_provider(
            mock_response=_stt_response(transcript=None),
        )
        with pytest.raises(SarvamError, match="not a string"):
            provider.transcribe_audio(b"audio")

    def test_transcribe_audio_rejects_empty_transcript(self):
        """Whitespace-only transcript → SarvamError."""
        provider = self._make_provider(
            mock_response=_stt_response(transcript="   "),
        )
        with pytest.raises(SarvamError, match="empty"):
            provider.transcribe_audio(b"audio")

    def test_transcribe_audio_defaults_missing_confidence(self):
        """Missing confidence field → defaults to 0.0."""
        provider = self._make_provider(
            mock_response={
                "transcript": "hello world",
                "language_code": "en-IN",
            },
        )
        result = provider.transcribe_audio(b"audio")
        assert result.transcript == "hello world"
        assert result.detected_language == "en-IN"
        assert result.confidence == 0.0

    def test_transcribe_audio_defaults_missing_language_code(self):
        """Missing language_code field → defaults to 'hi-IN'."""
        provider = self._make_provider(
            mock_response={
                "transcript": "hello world",
                "confidence": 0.88,
            },
        )
        result = provider.transcribe_audio(b"audio")
        assert result.transcript == "hello world"
        assert result.detected_language == "hi-IN"
        assert result.confidence == 0.88

    # ── privacy: no logging of transcript ───────────────────────

    def test_transcribe_audio_does_not_log_transcript(self, caplog):
        """The transcript must never appear in logs."""
        import logging

        transcript = "sensitive ward 8 complaint about water"
        provider = self._make_provider(
            mock_response=_stt_response(transcript=transcript),
        )
        with caplog.at_level(logging.DEBUG):
            provider.transcribe_audio(b"audio")

        assert transcript not in caplog.text


# ── TranscribeAudioTranslate tests ────────────────────────────────────


class TestTranscribeAudioTranslate:
    """All transcribe_audio_translate tests use FakeSarvamClient — zero HTTP."""

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_provider(
        mock_response: Optional[Dict[str, Any]] = None,
        settings_overrides: Optional[Dict[str, Any]] = None,
    ) -> SarvamAIProvider:
        """Build a SarvamAIProvider wired to a FakeSarvamClient."""
        import app.services.ai_provider as mod

        overrides = dict(settings_overrides or {})
        overrides.setdefault("sarvam_api_key", "fake-key-for-tests")
        overrides.setdefault("sarvam_stt_translate_model", "saaras:v2.5")
        overrides.setdefault("sarvam_api_base", "https://api.sarvam.ai")
        overrides.setdefault("sarvam_timeout_seconds", 30.0)
        overrides.setdefault("sarvam_max_retries", 0)

        test_settings = Settings(_env_file=None, **overrides)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mod, "get_settings", lambda: test_settings)

        fake_client = FakeSarvamClient(response=mock_response)
        provider = SarvamAIProvider(client=fake_client)
        provider._test_monkeypatch = monkeypatch  # type: ignore[attr-defined]
        return provider

    # ── happy path ──────────────────────────────────────────────

    def test_transcribe_audio_translate_returns_transcription_result(self):
        """Happy path: returns TranscriptionResult with transcript, language, confidence."""
        provider = self._make_provider(
            mock_response=_stt_response(
                transcript="water supply is affected in ward 8",
                language_code="en-IN",
                confidence=0.93,
            ),
        )
        result = provider.transcribe_audio_translate(b"fake wav audio")
        assert result.transcript == "water supply is affected in ward 8"
        assert result.detected_language == "en-IN"
        assert result.confidence == 0.93
        assert isinstance(result.confidence, float)

    # ── endpoint verification ───────────────────────────────────

    def test_transcribe_audio_translate_calls_stt_translate_endpoint_without_language_code(self):
        """Verify /speech-to-text-translate path, model, and audio_bytes; language is omitted for auto-detect."""
        provider = self._make_provider(mock_response=_stt_response())
        audio = b"dummy audio content"
        provider.transcribe_audio_translate(audio, target_language="en-IN")
        fake = provider.client
        assert len(fake.calls) == 1
        call = fake.calls[0]  # (path, audio_bytes, model, language)
        assert call[0] == "/speech-to-text-translate"
        assert call[1] == audio
        assert call[2] == "saaras:v2.5"
        assert call[3] is None

    # ── defaults ────────────────────────────────────────────────

    def test_transcribe_audio_translate_omits_language_code_for_auto_detect(self):
        """Default STT-translate omits language_code so Sarvam auto-detects speech."""
        provider = self._make_provider(mock_response=_stt_response())
        provider.transcribe_audio_translate(b"audio")
        fake = provider.client
        _, _, _, language = fake.calls[0]
        assert language is None

    # ── size validation ─────────────────────────────────────────

    def test_transcribe_audio_translate_rejects_audio_over_10mb(self):
        """Audio > 10 MB raises SarvamError before any API call."""
        provider = self._make_provider(mock_response=_stt_response())
        large_audio = b"x" * (10 * 1024 * 1024 + 1)
        with pytest.raises(SarvamError, match="10"):
            provider.transcribe_audio_translate(large_audio)
        fake = provider.client
        assert len(fake.calls) == 0

    # ── response extraction ─────────────────────────────────────

    def test_transcribe_audio_translate_handles_missing_fields(self):
        """Missing confidence and language_code → defaults (0.0, 'en-IN')."""
        provider = self._make_provider(
            mock_response={"transcript": "hello world"},
        )
        result = provider.transcribe_audio_translate(b"audio")
        assert result.transcript == "hello world"
        assert result.detected_language == "en-IN"
        assert result.confidence == 0.0

    # ── privacy: no logging of transcript ───────────────────────

    def test_transcribe_audio_translate_does_not_log_transcript(self, caplog):
        """The transcript must never appear in logs."""
        import logging

        transcript = "sensitive ward 8 complaint about water supply"
        provider = self._make_provider(
            mock_response=_stt_response(transcript=transcript),
        )
        with caplog.at_level(logging.DEBUG):
            provider.transcribe_audio_translate(b"audio")
        assert transcript not in caplog.text


# ── synthesize_speech tests ────────────────────────────────────────────


class TestSynthesizeSpeech:
    """All synthesize_speech tests use FakeSarvamClient — zero HTTP."""

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _make_provider(
        mock_response: Optional[Dict[str, Any]] = None,
    ) -> SarvamAIProvider:
        """Build a SarvamAIProvider wired to a FakeSarvamClient."""
        import app.services.ai_provider as mod

        settings_overrides = {
            "sarvam_api_key": "fake-key-for-tests",
            "sarvam_tts_model": "bulbul:v3",
            "sarvam_api_base": "https://api.sarvam.ai",
            "sarvam_timeout_seconds": 30.0,
            "sarvam_max_retries": 0,
        }

        test_settings = Settings(_env_file=None, **settings_overrides)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(mod, "get_settings", lambda: test_settings)

        fake_client = FakeSarvamClient(response=mock_response)
        try:
            return SarvamAIProvider(client=fake_client)
        finally:
            monkeypatch.undo()

    @staticmethod
    def _tts_response(audio_data: bytes = b"hello speech") -> Dict[str, Any]:
        """Return a Sarvam TTS response with base64-encoded audio."""
        import base64

        encoded = base64.b64encode(audio_data).decode("ascii")
        return {"audios": [encoded]}

    # ── happy path ──────────────────────────────────────────────

    def test_synthesize_speech_returns_decoded_bytes(self):
        """Happy path: returns decoded bytes from audios[0]."""
        expected_audio = b"hello speech"
        mock_response = self._tts_response(audio_data=expected_audio)
        provider = self._make_provider(mock_response=mock_response)

        result = provider.synthesize_speech("hello")

        assert isinstance(result, bytes)
        assert result == expected_audio

    # ── endpoint verification ───────────────────────────────────

    def test_synthesize_speech_calls_text_to_speech_endpoint(self):
        """Verify POST /text-to-speech with model, language, text in payload."""
        provider = self._make_provider(
            mock_response=self._tts_response(),
        )

        provider.synthesize_speech("hello world", language="ta-IN", speaker="meera")

        fake = provider.client
        assert len(fake.calls) == 1
        path, payload = fake.calls[0]
        assert path == "/text-to-speech"
        assert payload["model"] == "bulbul:v3"
        assert payload["inputs"] == ["hello world"]
        assert payload["target_language_code"] == "ta-IN"
        assert payload["speaker"] == "meera"

    # ── validation ──────────────────────────────────────────────

    def test_synthesize_speech_rejects_text_over_500_chars(self):
        """Text > 500 characters raises SarvamError before any API call."""
        provider = self._make_provider(
            mock_response=self._tts_response(),
        )
        long_text = "x" * 501

        with pytest.raises(SarvamError, match="500"):
            provider.synthesize_speech(long_text)

        fake = provider.client
        assert len(fake.calls) == 0

    # ── defaults ────────────────────────────────────────────────

    def test_synthesize_speech_defaults_language_and_speaker(self):
        """Default language='hi-IN' and speaker='aditya' when not provided."""
        provider = self._make_provider(
            mock_response=self._tts_response(),
        )

        provider.synthesize_speech("hello")

        fake = provider.client
        _, payload = fake.calls[0]
        assert payload["target_language_code"] == "hi-IN"
        assert payload["speaker"] == "aditya"

    # ── privacy: no logging of text ──────────────────────────────

    def test_synthesize_speech_does_not_log_text(self, caplog):
        """The text must never appear in logs (privacy)."""
        import logging

        sensitive_text = "sensitive ward 8 complaint about water supply"
        provider = self._make_provider(
            mock_response=self._tts_response(),
        )

        with caplog.at_level(logging.DEBUG):
            provider.synthesize_speech(sensitive_text)

        assert sensitive_text not in caplog.text
