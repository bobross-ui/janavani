import logging
import re
import time
from typing import Callable, Dict, Optional, Protocol

from app.config import get_settings
from app.schemas import ExtractionResult
from app.services.extraction import extract_grievance
from app.services.redaction import redact_all
from app.services.sarvam_client import SarvamClient, SarvamError


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
    """Sarvam AI provider — requires SARVAM_API_KEY in environment.

    Accepts an optional *client* (SarvamClient) for dependency injection
    so tests can supply a mock without touching real HTTP.
    """

    def __init__(self, client: Optional[SarvamClient] = None) -> None:
        settings = get_settings()

        if client is not None:
            self._client = client
            return

        if not settings.sarvam_api_key:
            raise NotImplementedError(
                "Sarvam AI provider requires SARVAM_API_KEY in environment. "
                "Set SARVAM_API_KEY=... in .env and configure AI_PROVIDER=sarvam."
            )
        self._client = SarvamClient(
            api_key=settings.sarvam_api_key,
            base_url=settings.sarvam_api_base,
            timeout=settings.sarvam_timeout_seconds,
            max_retries=settings.sarvam_max_retries,
        )

    @property
    def client(self) -> SarvamClient:
        """Expose the wrapped SarvamClient for introspection in tests."""
        return self._client

    # ── PII guards (post‑generation) ────────────────────────────

    _PHONE_RE = re.compile(r"\b\d{10}\b")
    _EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

    @classmethod
    def _check_pii_leak(cls, text: str) -> None:
        """Raise SarvamError if *text* contains 10‑digit phone or email."""
        if cls._PHONE_RE.search(text) or cls._EMAIL_RE.search(text):
            raise SarvamError("draft contained possible PII leak")

    # ── generate_draft ──────────────────────────────────────────

    def generate_draft(self, cluster_context: dict) -> str:
        """Generate a formal civic complaint draft via Sarvam chat completion.

        Parameters
        ----------
        cluster_context : dict
            Must contain at least ``title``, ``department``, ``area``,
            ``language``, ``ward``, ``grievance_count``, ``summary``, and
            ``sample_grievances`` (list of dicts with ``pii_redacted_text``).

        Returns
        -------
        str
            The generated draft text.

        Raises
        ------
        SarvamError
            If the API call fails or the response leaks PII.
        """
        settings = get_settings()

        department = cluster_context.get("department", "concerned department")
        language = cluster_context.get("language", "en")
        area = cluster_context.get("area", "the affected area")

        # ── system prompt ─────────────────────────────────────

        system_prompt = (
            "You are drafting a formal civic complaint in {language}. "
            "Use only facts from the supplied grievances. "
            "Do not invent names, phone numbers, dates, or statistics. "
            "Output should be respectful, formal, and addressed to {department}."
        ).format(language=language, department=department)

        # ── user prompt ───────────────────────────────────────

        title = cluster_context.get("title", "Public Grievance")
        ward = cluster_context.get("ward", "")
        grievance_count = cluster_context.get("grievance_count", 0)
        summary = cluster_context.get("summary", "")

        samples = cluster_context.get("sample_grievances", [])
        # Only use pii_redacted_text — never raw_text
        grievances_list: list = []
        for g in samples[:5]:
            if isinstance(g, dict):
                grievances_list.append(g.get("pii_redacted_text", g.get("raw_text", "")))

        grievances_block = "\n".join(
            f"  {i}. {t}" for i, t in enumerate(grievances_list, 1) if t
        )

        user_prompt = (
            "Cluster Title: {title}\n"
            "Department: {department}\n"
            "Ward: {ward}\n"
            "Area: {area}\n"
            "Grievance Count: {count}\n"
            "Summary: {summary}\n\n"
            "Sample Grievances:\n"
            "{grievances}\n\n"
            "Write a formal complaint letter to the {department} on behalf of "
            "{count} citizens of {area}."
        ).format(
            title=title,
            department=department,
            ward=ward,
            area=area,
            count=grievance_count,
            summary=summary,
            grievances=grievances_block or "(none)",
        )

        # ── chat completion payload ────────────────────────────

        payload: Dict = {
            "model": settings.sarvam_chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        response = self._client.post_json("/v1/chat/completions", payload)
        try:
            draft_text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SarvamError("Unexpected chat completion response shape") from exc

        if not isinstance(draft_text, str) or not draft_text.strip():
            raise SarvamError("Chat completion response content was empty or not a string")

        # ── post‑generation PII check ──────────────────────────

        self._check_pii_leak(draft_text)
        return draft_text

    # ── remaining stubs ───────────────────────────────────────

    def transcribe_audio(self, audio_bytes: bytes) -> str:
        raise NotImplementedError("Sarvam STT not yet implemented")

    def translate_text(self, text: str, target_language: str) -> str:
        raise NotImplementedError("Sarvam translation not yet implemented")

    def extract_grievance(
        self, text: str, language: str = "hi"
    ) -> ExtractionResult:
        raise NotImplementedError("Sarvam extraction not yet implemented")


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
