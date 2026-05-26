"""Tests for POST /grievances/audio endpoint.

TDD tests written BEFORE the implementation. Follows the exact same
pattern as test_grievance_flow.py: in-memory SQLite + TestClient +
dependency_overrides.
"""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import (  # noqa: F401
    ClusterSupport,
    ComplaintDraft,
    EvalRun,
    Grievance,
    IssueCluster,
    User,
)
from app.schemas import ExtractionResult, TranscriptionResult
from app.services.ai_provider import AIProvider
from app.services.audio_storage import AudioStorage
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


def _seed_user(session: Session) -> User:
    user = User(phone_number="9876543210", ward="8")
    session.add(user)
    session.commit()
    return user


def _fake_audio_bytes() -> bytes:
    """Return a tiny WAV-like byte sequence for testing."""
    # Minimal WAV header (44 bytes) + silence data
    header = (
        b"RIFF"
        b"\x28\x00\x00\x00"  # ChunkSize (36 + data)
        b"WAVE"
        b"fmt "
        b"\x10\x00\x00\x00"  # Subchunk1Size (16)
        b"\x01\x00"          # AudioFormat (1 = PCM)
        b"\x01\x00"          # NumChannels (1)
        b"\x80\x3e\x00\x00"  # SampleRate (16000)
        b"\x00\x7d\x00\x00"  # ByteRate (32000)
        b"\x02\x00"          # BlockAlign (2)
        b"\x10\x00"          # BitsPerSample (16)
        b"data"
        b"\x04\x00\x00\x00"  # Subchunk2Size (4)
        b"\x00\x00\x00\x00"  # 4 bytes of silence
    )
    return header


# ── mock provider ──────────────────────────────────────────────────────


class _MockTranscribeProvider:
    """Mock AIProvider that returns a controlled TranscriptionResult."""

    def __init__(
        self,
        transcript: str = "paani nahi aa raha ward 8 mein",
        detected_language: str = "hi-IN",
        confidence: float = 0.95,
    ):
        self._transcript = transcript
        self._detected_language = detected_language
        self._confidence = confidence
        self.transcribe_called = False
        self.transcribe_translate_called = False
        self.transcribe_audio_bytes = None
        self.transcribe_language = None
        self.transcribe_translate_target_language = None

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        language_code: str = "hi-IN",
        model: str = None,
    ) -> TranscriptionResult:
        self.transcribe_called = True
        self.transcribe_audio_bytes = audio_bytes
        self.transcribe_language = language_code
        return TranscriptionResult(
            transcript=self._transcript,
            detected_language=self._detected_language,
            confidence=self._confidence,
        )

    def transcribe_audio_translate(
        self,
        audio_bytes: bytes,
        target_language: str = "en-IN",
        model: str = None,
    ) -> TranscriptionResult:
        self.transcribe_translate_called = True
        self.transcribe_audio_bytes = audio_bytes
        self.transcribe_translate_target_language = target_language
        return TranscriptionResult(
            transcript=self._transcript,
            detected_language=self._detected_language,
            confidence=self._confidence,
        )

    def translate_text(
        self, text: str, target_language: str,
        source_language: str = None,
    ) -> str:
        return text  # no-op for test

    def extract_grievance(
        self, text: str, language: str = "hi"
    ) -> ExtractionResult:
        # Use the real extraction pipeline
        from app.services.extraction import extract_grievance
        result = extract_grievance(text, language)
        result.pii_redacted_text = result.normalized_text
        return result

    def generate_draft(self, cluster_context: dict) -> str:
        return "test draft"



class _ErrorTranscribeProvider:
    """Mock that raises SarvamError on transcribe."""

    def transcribe_audio(self, *args, **kwargs) -> TranscriptionResult:
        raise SarvamError("STT service unavailable")

    def transcribe_audio_translate(self, *args, **kwargs) -> TranscriptionResult:
        raise SarvamError("STT translate service unavailable")

    def translate_text(self, *args, **kwargs) -> str:
        return args[0]

    def extract_grievance(self, *args, **kwargs) -> ExtractionResult:
        from app.services.extraction import extract_grievance
        r = extract_grievance(*args, **kwargs)
        r.pii_redacted_text = r.normalized_text
        return r

    def generate_draft(self, *args, **kwargs) -> str:
        return "test draft"


# ── mock audio storage ─────────────────────────────────────────────────


class _MockAudioStorage:
    """Mock AudioStorage for testing — records calls and returns fake keys."""

    def __init__(self, fake_key: str = "2025-01-01/mock-audio.wav"):
        self._fake_key = fake_key
        self.save_called = False
        self.saved_bytes = None
        self.saved_content_type = None

    def save_audio(self, audio_bytes: bytes, content_type: str) -> str:
        self.save_called = True
        self.saved_bytes = audio_bytes
        self.saved_content_type = content_type
        return self._fake_key

    def load_audio(self, key: str) -> bytes:
        return b"fake"

    def delete_audio(self, key: str) -> None:
        pass


# ── helper to set up dependencies ──────────────────────────────────────


def _install_mocks(mock_provider, mock_storage):
    """Override FastAPI dependencies with test mocks."""
    from app.routes.grievances import get_audio_storage, get_request_ai_provider

    def override_provider():
        return mock_provider

    def override_storage():
        return mock_storage

    app.dependency_overrides[get_request_ai_provider] = override_provider
    app.dependency_overrides[get_audio_storage] = override_storage


class TestLocalProviderVoiceSupport:
    def test_local_provider_stt_translate_fails_instead_of_returning_empty_transcript(self):
        """Local provider has no STT-translate; it must fail instead of saving blank grievances."""
        from app.services.ai_provider import LocalAIProvider

        provider = LocalAIProvider()
        with pytest.raises(SarvamError, match="not available"):
            provider.transcribe_audio_translate(b"fake audio")


# ── tests ──────────────────────────────────────────────────────────────


class TestAudioEndpoint:
    def setup_method(self):
        self.engine = _setup_test_db()
        self.client = TestClient(app)

    def _session(self):
        return Session(self.engine)

    # ── test 1: happy path ─────────────────────────────────────────

    def test_audio_submission_returns_grievance_response(self):
        """Upload fake audio + verify response structure."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider()
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        audio_bytes = _fake_audio_bytes()
        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("test.wav", BytesIO(audio_bytes), "audio/wav")},
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "true",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Check top-level keys
        assert "grievance" in data
        assert "extraction" in data
        assert "suggested_action" in data

        # Check grievance fields
        g = data["grievance"]
        assert g["user_id"] == user.id
        assert g["raw_text"] == "paani nahi aa raha ward 8 mein"
        assert g["audio_key"] == "2025-01-01/mock-audio.wav"
        assert g["issue_category"]
        assert g["status"] == "clustered"

        # Check extraction
        assert "category" in data["extraction"]

    # ── test 2: persistence with audio_key ────────────────────────

    def test_audio_submission_persists_grievance_with_audio_key(self):
        """Verify DB record has audio_key."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider()
        mock_storage = _MockAudioStorage(fake_key="2025-05-25/abc123.mp3")
        _install_mocks(mock_provider, mock_storage)

        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("recording.mp3", BytesIO(_fake_audio_bytes()), "audio/mpeg")},
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "false",
            },
        )

        assert resp.status_code == 200, resp.text
        gid = resp.json()["grievance"]["id"]

        # Query DB directly
        grievance = session.get(Grievance, gid)
        assert grievance is not None
        assert grievance.audio_key == "2025-05-25/abc123.mp3"

    # ── test 3: transcription → extraction pipeline ───────────────

    def test_audio_submission_translates_and_extracts(self):
        """Verify provider.transcribe_audio_translate called, then extraction runs on transcript."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider(
            transcript="ward 8 paani ki samasya",
            detected_language="hi-IN",
            confidence=0.88,
        )
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("test.wav", BytesIO(_fake_audio_bytes()), "audio/wav")},
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "true",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()

        # transcribe_audio_translate was called; the legacy language form field is ignored.
        assert mock_provider.transcribe_translate_called
        assert not mock_provider.transcribe_called
        assert mock_provider.transcribe_translate_target_language == "en-IN"
        assert mock_provider.transcribe_audio_bytes is not None

        # raw_text in grievance = transcript
        assert data["grievance"]["raw_text"] == "ward 8 paani ki samasya"

        # extraction ran on the transcript
        assert data["extraction"]["category"] == "water_supply"

    def test_audio_submission_auto_detects_and_translates_without_language_selection(self):
        """Voice uploads should not require user language selection.

        The backend should use STT-translate so Sarvam auto-detects the spoken
        language and returns an English transcript for extraction.
        """
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider(
            transcript="There has been no water in ward 8 for four days",
            detected_language="mr-IN",
            confidence=0.91,
        )
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("test.wav", BytesIO(_fake_audio_bytes()), "audio/wav")},
            data={
                "user_id": user.id,
                "consent_public": "true",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert mock_provider.transcribe_translate_called
        assert not mock_provider.transcribe_called
        assert data["grievance"]["raw_text"] == "There has been no water in ward 8 for four days"
        assert data["grievance"]["language"] == "mr-IN"
        assert data["grievance"]["issue_category"] == "water_supply"
        assert data["grievance"]["ward"] == "8"

    # ── test 4: missing audio file → 422 ─────────────────────────

    def test_audio_submission_rejects_missing_audio_file(self):
        """Missing audio file → 422 or 400."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider()
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        resp = self.client.post(
            "/grievances/audio",
            files={},  # no audio file
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "true",
            },
        )

        assert resp.status_code in (400, 422), (
            f"Expected 400 or 422, got {resp.status_code}: {resp.text}"
        )

    # ── test 5: large audio rejection ────────────────────────────

    def test_audio_submission_rejects_large_audio(self):
        """Audio larger than 10 MB → rejected with 413 or 400."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider()
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        # Create audio bytes larger than 10 MB
        large_audio = b"\x00" * (11 * 1024 * 1024)  # 11 MB

        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("huge.wav", BytesIO(large_audio), "audio/wav")},
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "true",
            },
        )

        assert resp.status_code in (400, 413), (
            f"Expected 400 or 413, got {resp.status_code}: {resp.text}"
        )

    # ── test 6: storage service called ────────────────────────────

    def test_audio_submission_stores_audio_via_storage_service(self):
        """Verify AudioStorage.save_audio called with correct bytes + content type."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _MockTranscribeProvider()
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        audio_bytes = _fake_audio_bytes()
        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("recording.wav", BytesIO(audio_bytes), "audio/wav")},
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "true",
            },
        )

        assert resp.status_code == 200, resp.text
        assert mock_storage.save_called
        assert mock_storage.saved_bytes == audio_bytes
        assert mock_storage.saved_content_type == "audio/wav"

    # ── test 7: transcription error → controlled response ────────

    def test_audio_submission_handles_transcription_error(self):
        """SarvamError from transcribe → controlled error response."""
        session = self._session()
        user = _seed_user(session)

        mock_provider = _ErrorTranscribeProvider()
        mock_storage = _MockAudioStorage()
        _install_mocks(mock_provider, mock_storage)

        resp = self.client.post(
            "/grievances/audio",
            files={"audio": ("test.wav", BytesIO(_fake_audio_bytes()), "audio/wav")},
            data={
                "user_id": user.id,
                "language": "hi-IN",
                "consent_public": "true",
            },
        )

        # Should get a 502 or 503 error with details
        assert resp.status_code in (502, 503), (
            f"Expected 502 or 503, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert "detail" in data
