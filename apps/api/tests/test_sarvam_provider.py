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
