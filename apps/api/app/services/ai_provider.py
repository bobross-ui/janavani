from typing import Optional, Protocol

from app.config import get_settings
from app.schemas import ExtractionResult
from app.services.extraction import extract_grievance
from app.services.redaction import redact_all


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


# ── Factory ───────────────────────────────────────────────────────────


def get_ai_provider() -> AIProvider:
    """Return the configured AI provider based on settings."""
    settings = get_settings()
    if settings.ai_provider == "sarvam":
        return SarvamAIProvider()
    return LocalAIProvider()
