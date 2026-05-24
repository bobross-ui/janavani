import logging
import time
from typing import Callable, Optional, Protocol

from app.config import get_settings
from app.schemas import ExtractionResult
from app.services.extraction import extract_grievance
from app.services.redaction import redact_all
from app.services.sarvam_client import SarvamError


logger = logging.getLogger(__name__)


# ── Provider protocol ─────────────────────────────────────────────────


class AIProvider(Protocol):
    """Interface for AI providers. Implementations can be swapped at runtime."""

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Convert audio bytes to text transcript."""
        ...

    def translate_text(self, text: str, target_language: str) -> str:
        """Translate text to target language."""
        ...

    def extract_grievance(self, text: str, language: str = "hi") -> ExtractionResult:
        """Extract structured fields from grievance text."""
        ...

    def generate_draft(self, cluster_context: dict) -> str:
        """Generate a formal complaint draft from cluster context."""
        ...


# ── Local provider ────────────────────────────────────────────────────


class LocalAIProvider:
    """Deterministic local provider — no API keys needed."""

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        return "[local: audio transcription not available]"

    def translate_text(self, text: str, target_language: str) -> str:
        return text  # no-op for local

    def extract_grievance(
        self, text: str, language: str = "hi"
    ) -> ExtractionResult:
        result = extract_grievance(text, language)
        result.pii_redacted_text = redact_all(result.normalized_text)
        return result

    def generate_draft(self, cluster_context: dict) -> str:
        title = cluster_context.get("title", "Public Grievance")
        department = cluster_context.get("department", "concerned department")
        area = cluster_context.get("area", "the affected area")
        count = cluster_context.get("grievance_count", 0)
        summary = cluster_context.get("summary", "Multiple citizens have reported this issue.")

        return (
            f"To,\n"
            f"The {department.title()},\n\n"
            f"Subject: {title}\n\n"
            f"Respected Sir/Madam,\n\n"
            f"We, the undersigned {count} citizens of {area}, wish to bring "
            f"the following issue to your attention:\n\n"
            f"{summary}\n\n"
            f"This issue has been reported by {count} citizens and is affecting "
            f"daily life in {area}. We request immediate action to resolve this matter.\n\n"
            f"Thank you,\n"
            f"Citizens of {area}"
        )


# ── Sarvam provider (placeholder) ─────────────────────────────────────


class SarvamAIProvider:
    """Sarvam AI provider — requires SARVAM_API_KEY in environment."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.sarvam_api_key:
            raise NotImplementedError(
                "Sarvam AI provider requires SARVAM_API_KEY in environment. "
                "Set SARVAM_API_KEY=... in .env and configure AI_PROVIDER=sarvam."
            )

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        raise NotImplementedError("Sarvam STT not yet implemented")

    def translate_text(self, text: str, target_language: str) -> str:
        raise NotImplementedError("Sarvam translation not yet implemented")

    def extract_grievance(
        self, text: str, language: str = "hi"
    ) -> ExtractionResult:
        raise NotImplementedError("Sarvam extraction not yet implemented")

    def generate_draft(self, cluster_context: dict) -> str:
        raise NotImplementedError("Sarvam draft generation not yet implemented")


# ── Fallback provider and circuit breaker ─────────────────────────────


class CircuitBreaker:
    """Small in-memory circuit breaker for Sarvam fallback decisions."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
        failure_window_seconds: float = 60.0,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_seconds = recovery_seconds
        self.failure_window_seconds = failure_window_seconds
        self.time_func = time_func
        self.consecutive_failures = 0
        self.first_failure_at: Optional[float] = None
        self.opened_at: Optional[float] = None

    def allow_request(self) -> bool:
        if self.opened_at is None:
            return True
        return (self.time_func() - self.opened_at) >= self.recovery_seconds

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.first_failure_at = None
        self.opened_at = None

    def record_failure(self) -> None:
        now = self.time_func()
        if self.opened_at is not None:
            self.consecutive_failures = self.failure_threshold
            self.first_failure_at = now
            self.opened_at = now
            return

        if (
            self.first_failure_at is None
            or (now - self.first_failure_at) > self.failure_window_seconds
        ):
            self.first_failure_at = now
            self.consecutive_failures = 0

        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at = now


_sarvam_circuit_breaker = CircuitBreaker()


def _reset_sarvam_circuit_breaker_for_tests() -> None:
    _sarvam_circuit_breaker.record_success()


class FallbackAIProvider:
    """AI provider wrapper that falls back to a local provider on Sarvam errors."""

    def __init__(
        self,
        primary: AIProvider,
        fallback: AIProvider,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        return self._call_with_fallback(
            "transcribe_audio",
            self.primary.transcribe_audio,
            self.fallback.transcribe_audio,
            audio_bytes,
        )

    def translate_text(self, text: str, target_language: str) -> str:
        return self._call_with_fallback(
            "translate_text",
            self.primary.translate_text,
            self.fallback.translate_text,
            text,
            target_language,
        )

    def extract_grievance(
        self, text: str, language: str = "hi"
    ) -> ExtractionResult:
        return self._call_with_fallback(
            "extract_grievance",
            self.primary.extract_grievance,
            self.fallback.extract_grievance,
            text,
            language,
        )

    def generate_draft(self, cluster_context: dict) -> str:
        return self._call_with_fallback(
            "generate_draft",
            self.primary.generate_draft,
            self.fallback.generate_draft,
            cluster_context,
        )

    def _call_with_fallback(self, method_name: str, primary_call, fallback_call, *args):
        if not self.circuit_breaker.allow_request():
            logger.warning(
                "Sarvam circuit open for %s; falling back to local AI provider",
                method_name,
            )
            return fallback_call(*args)

        try:
            result = primary_call(*args)
        except SarvamError as exc:
            self.circuit_breaker.record_failure()
            logger.warning(
                "Sarvam provider failed for %s (%s); falling back to local AI provider",
                method_name,
                exc.__class__.__name__,
            )
            return fallback_call(*args)

        self.circuit_breaker.record_success()
        return result


# ── Factory ───────────────────────────────────────────────────────────


def get_ai_provider() -> AIProvider:
    """Return the configured AI provider based on settings."""
    settings = get_settings()
    if settings.ai_provider == "sarvam":
        if settings.sarvam_fallback_on_error:
            try:
                return FallbackAIProvider(
                    SarvamAIProvider(),
                    LocalAIProvider(),
                    circuit_breaker=_sarvam_circuit_breaker,
                )
            except NotImplementedError as exc:
                logger.warning(
                    "Sarvam provider unavailable during initialization (%s); "
                    "falling back to local AI provider",
                    exc.__class__.__name__,
                )
                return LocalAIProvider()
        return SarvamAIProvider()
    return LocalAIProvider()
