"""Tests for POST /tts endpoint.

TDD tests written BEFORE the implementation. Follows the exact same
pattern as test_audio_endpoint.py: in-memory SQLite + TestClient +
dependency_overrides.
"""

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import (  # noqa: F401 - ensure all tables registered
    ClusterSupport,
    ComplaintDraft,
    EvalRun,
    Grievance,
    IssueCluster,
    User,
)
from app.services.sarvam_client import SarvamError


# ── helpers ────────────────────────────────────────────────────────────


def _setup_test_db():
    engine = create_engine(
        "sqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return engine


# ── mock providers ─────────────────────────────────────────────────────


class _MockTTSProvider:
    """Mock AIProvider that returns controlled audio/wav bytes."""

    def __init__(self, audio_bytes: bytes = b"fake-wav-data"):
        self._audio_bytes = audio_bytes
        self.synthesize_speech_called = False
        self.synthesize_text = None
        self.synthesize_language = None
        self.synthesize_speaker = None

    def synthesize_speech(
        self,
        text: str,
        language: str = "hi-IN",
        speaker: str = "aditya",
    ) -> bytes:
        self.synthesize_speech_called = True
        self.synthesize_text = text
        self.synthesize_language = language
        self.synthesize_speaker = speaker
        return self._audio_bytes


class _ErrorTTSProvider:
    """Mock that raises SarvamError on synthesize_speech."""

    def synthesize_speech(self, *args, **kwargs) -> bytes:
        raise SarvamError("TTS service unavailable")


# ── helper to set up dependencies ──────────────────────────────────────


def _install_tts_mock(mock_provider):
    """Override FastAPI dependencies with a mock TTS provider."""
    from app.routes.grievances import get_request_ai_provider

    def override_provider():
        return mock_provider

    app.dependency_overrides[get_request_ai_provider] = override_provider


# ── tests ──────────────────────────────────────────────────────────────


class TestTTSEndpoint:
    def setup_method(self):
        self.engine = _setup_test_db()
        self.client = TestClient(app)

    def _session(self):
        return Session(self.engine)

    # ── test 1: happy path ─────────────────────────────────────────

    def test_tts_returns_audio_wav_bytes(self):
        """POST /tts with valid text → 200, content-type audio/wav, returns bytes."""
        expected_audio = b"fake-wav-data"
        mock_provider = _MockTTSProvider(audio_bytes=expected_audio)
        _install_tts_mock(mock_provider)

        resp = self.client.post(
            "/tts",
            json={
                "text": "namaste duniya",
                "language": "hi-IN",
                "speaker": "aditya",
            },
        )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        assert resp.headers["content-type"] == "audio/wav", (
            f"Expected content-type audio/wav, got {resp.headers.get('content-type')}"
        )
        assert resp.content == expected_audio

    # ── test 2: text > 500 chars → 400 ─────────────────────────────

    def test_tts_rejects_text_over_500_chars(self):
        """POST /tts with text > 500 characters → 400."""
        mock_provider = _MockTTSProvider()
        _install_tts_mock(mock_provider)

        long_text = "x" * 501
        resp = self.client.post(
            "/tts",
            json={
                "text": long_text,
                "language": "hi-IN",
                "speaker": "aditya",
            },
        )

        assert resp.status_code == 400, (
            f"Expected 400, got {resp.status_code}: {resp.text}"
        )

    # ── test 3: provider called with correct args ──────────────────

    def test_tts_calls_provider_synthesize_speech(self):
        """Provider.synthesize_speech called with correct text, language, speaker."""
        mock_provider = _MockTTSProvider()
        _install_tts_mock(mock_provider)

        resp = self.client.post(
            "/tts",
            json={
                "text": "hello world",
                "language": "ta-IN",
                "speaker": "meera",
            },
        )

        # Check response status first (will fail RED since route absent)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )

        # Verify provider was called with correct arguments
        assert mock_provider.synthesize_speech_called, (
            "Expected synthesize_speech to be called"
        )
        assert mock_provider.synthesize_text == "hello world"
        assert mock_provider.synthesize_language == "ta-IN"
        assert mock_provider.synthesize_speaker == "meera"

    # ── test 4: defaults when optional fields omitted ──────────────

    def test_tts_uses_defaults_for_optional_fields(self):
        """Omitted language and speaker → defaults of 'hi-IN' and 'aditya'."""
        mock_provider = _MockTTSProvider()
        _install_tts_mock(mock_provider)

        resp = self.client.post(
            "/tts",
            json={
                "text": "hello",
            },
        )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )

        # Defaults should be used when fields omitted
        assert mock_provider.synthesize_language == "hi-IN"
        assert mock_provider.synthesize_speaker == "aditya"

    # ── test 5: SarvamError → 502 with detail ──────────────────────

    def test_tts_returns_502_on_sarvam_error(self):
        """SarvamError from synthesize_speech → 502 with detail."""
        mock_provider = _ErrorTTSProvider()
        _install_tts_mock(mock_provider)

        resp = self.client.post(
            "/tts",
            json={
                "text": "hello",
                "language": "hi-IN",
                "speaker": "aditya",
            },
        )

        assert resp.status_code == 502, (
            f"Expected 502, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "detail" in data, (
            f"Expected 'detail' key in response, got keys: {list(data.keys())}"
        )
