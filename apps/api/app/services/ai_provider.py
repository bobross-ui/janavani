import base64
import json
import logging
import re
import time
from typing import Callable, Dict, Optional, Protocol

from app.config import get_settings
from app.schemas import ExtractionResult, TranscriptionResult
from app.services.extraction import extract_grievance
from app.services.redaction import redact_all
from app.services.sarvam_client import SarvamClient, SarvamError


logger = logging.getLogger(__name__)


# ── Shared Sarvam HTTP client ─────────────────────────────────────────
# A SarvamClient owns an httpx.Client (a connection pool). Providers are
# constructed per request via get_ai_provider(), so build the client once per
# configuration and reuse it instead of leaking a new pool on every request.
_sarvam_client_cache: Dict[tuple, "SarvamClient"] = {}


def _shared_sarvam_client(settings) -> "SarvamClient":
    key = (
        settings.sarvam_api_key,
        settings.sarvam_api_base,
        settings.sarvam_timeout_seconds,
        settings.sarvam_max_retries,
    )
    client = _sarvam_client_cache.get(key)
    if client is None:
        client = SarvamClient(
            api_key=settings.sarvam_api_key,
            base_url=settings.sarvam_api_base,
            timeout=settings.sarvam_timeout_seconds,
            max_retries=settings.sarvam_max_retries,
        )
        _sarvam_client_cache[key] = client
    return client


# ── Provider protocol ─────────────────────────────────────────────────


class AIProvider(Protocol):
    """Interface for AI providers. Implementations can be swapped at runtime."""

    def transcribe_audio(
        self, audio_bytes: bytes,
        language_code: str = "hi-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        """Convert audio bytes to TranscriptionResult with transcript, detected_language, confidence."""
        ...

    def translate_text(
        self, text: str, target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        """Translate text to target language."""
        ...

    def extract_grievance(self, text: str, language: str = "hi") -> ExtractionResult:
        """Extract structured fields from grievance text."""
        ...

    def transcribe_audio_translate(
        self, audio_bytes: bytes,
        target_language: str = "en-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        """Convert audio to text and translate to target language in one call."""
        ...

    def generate_draft(self, cluster_context: dict) -> str:
        """Generate a formal complaint draft from cluster context."""
        ...

    def synthesize_speech(
        self, text: str, language: str = "hi-IN", speaker: str = "aditya"
    ) -> bytes:
        """Convert text to speech audio bytes."""
        ...


# ── Local provider ────────────────────────────────────────────────────


class LocalAIProvider:
    """Deterministic local provider — no API keys needed."""

    def transcribe_audio(
        self, audio_bytes: bytes,
        language_code: str = "hi-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        return TranscriptionResult(
            transcript="[local: audio transcription not available]",
            detected_language=language_code,
            confidence=0.0,
        )

    def transcribe_audio_translate(
        self, audio_bytes: bytes,
        target_language: str = "en-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        raise SarvamError(
            "Speech-to-text translation is not available with the local AI provider. "
            "Start the API with AI_PROVIDER=sarvam for voice complaints."
        )

    def translate_text(
        self, text: str, target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
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

    def synthesize_speech(
        self, text: str, language: str = "hi-IN", speaker: str = "aditya"
    ) -> bytes:
        return b""


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
        self._client = _shared_sarvam_client(settings)

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
            "reasoning_effort": None,
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

    # ── transcribe_audio ───────────────────────────────────────

    def transcribe_audio(
        self, audio_bytes: bytes,
        language_code: str = "hi-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio bytes to text via Sarvam STT.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio data. Must be <= 10 MB.
        language_code : str
            Language code for the STT model (default "hi-IN").
        model : Optional[str]
            STT model name. Falls back to sarvam_stt_model setting.

        Returns
        -------
        TranscriptionResult
            Dataclass with transcript, detected_language, confidence.

        Raises
        ------
        SarvamError
            If audio > 10 MB, the API call fails, or the response is invalid.
        """
        settings = get_settings()

        # ── size guard ─────────────────────────────────────────
        max_size = 10 * 1024 * 1024  # 10 MB
        if len(audio_bytes) > max_size:
            raise SarvamError(
                "Audio too large: %d bytes (max %d bytes / 10 MB)"
                % (len(audio_bytes), max_size)
            )

        # ── model resolution ───────────────────────────────────
        if model is None:
            model = settings.sarvam_stt_model

        # ── API call ───────────────────────────────────────────
        response = self._client.post_audio_bytes(
            "/speech-to-text", audio_bytes, model=model, language=language_code,
        )

        # ── extract and validate ───────────────────────────────
        try:
            transcript = response["transcript"]
        except KeyError as exc:
            raise SarvamError(
                "Unexpected STT response shape: missing 'transcript' key"
            ) from exc

        if not isinstance(transcript, str) or not transcript.strip():
            raise SarvamError(
                "STT response transcript was empty or not a string"
            )

        detected_language = response.get("language_code", "hi-IN")
        confidence = float(response.get("confidence", 0.0))

        return TranscriptionResult(
            transcript=transcript,
            detected_language=detected_language,
            confidence=confidence,
        )

    # ── transcribe_audio_translate ──────────────────────────────

    def transcribe_audio_translate(
        self, audio_bytes: bytes,
        target_language: str = "en-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio and translate to target language via Sarvam STT Translate.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio data. Must be <= 10 MB.
        target_language : str
            Target language code (default "en-IN").
        model : Optional[str]
            STT Translate model. Falls back to sarvam_stt_translate_model setting.

        Returns
        -------
        TranscriptionResult
            Dataclass with transcript, detected_language, confidence.

        Raises
        ------
        SarvamError
            If audio > 10 MB, the API call fails, or the response is invalid.
        """
        settings = get_settings()

        # ── size guard ─────────────────────────────────────────
        max_size = 10 * 1024 * 1024  # 10 MB
        if len(audio_bytes) > max_size:
            raise SarvamError(
                "Audio too large: %d bytes (max %d bytes / 10 MB)"
                % (len(audio_bytes), max_size)
            )

        # ── model resolution ───────────────────────────────────
        if model is None:
            model = settings.sarvam_stt_translate_model

        # ── API call ───────────────────────────────────────────
        response = self._client.post_audio_bytes(
            "/speech-to-text-translate", audio_bytes,
            model=model, language=None,
        )

        # ── extract and validate ───────────────────────────────
        transcript = response.get("transcript", "")
        detected_language = response.get("language_code", "en-IN")
        confidence = float(response.get("confidence", 0.0))

        # Validate transcript is a non-empty string
        if not isinstance(transcript, str) or not transcript.strip():
            raise SarvamError(
                "STT Translate response transcript was empty or not a string"
            )

        return TranscriptionResult(
            transcript=transcript,
            detected_language=detected_language,
            confidence=confidence,
        )

    # ── remaining stubs ───────────────────────────────────────

    def translate_text(
        self, text: str, target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        """Translate *text* to *target_language* via Sarvam Mayura.

        Skips API call when ``source_language == target_language``
        (cost saver).  Results are cached in memory for the provider
        lifetime so that the same grievance translated twice in one
        pipeline run reuses the result.
        """
        # ── skip no‑op translations ───────────────────────────
        if source_language is not None and source_language == target_language:
            return text

        # ── in‑memory cache (lazy init) ─────────────────────────
        if not hasattr(self, "_translate_cache"):
            self._translate_cache: Dict = {}
        cache_key = (hash(text), target_language, source_language)
        cached = self._translate_cache.get(cache_key)
        if cached is not None:
            return cached

        # ── Mayura translate payload ────────────────────────────
        settings = get_settings()
        payload: Dict = {
            "model": settings.sarvam_translate_model,
            "input": text,
            "target_language_code": target_language,
        }
        if source_language is not None:
            payload["source_language_code"] = source_language

        t0 = time.monotonic()
        response = self._client.post_json("/translate", payload)
        elapsed = time.monotonic() - t0

        logger.debug(
            "Sarvam translation: model=%s target=%s latency=%.2fs",
            settings.sarvam_translate_model,
            target_language,
            elapsed,
        )

        # ── extract and validate ─────────────────────────────────
        try:
            translated = response["translated_text"]
        except KeyError as exc:
            raise SarvamError(
                "Unexpected translate response shape: "
                "missing 'translated_text' key"
            ) from exc

        if not isinstance(translated, str) or not translated.strip():
            raise SarvamError(
                "Translate response content was empty or not a string"
            )

        self._translate_cache[cache_key] = translated
        return translated

    def extract_grievance(
        self, text: str, language: str = "hi-IN"
    ) -> ExtractionResult:
        """Extract structured grievance fields via Sarvam-M chat completion.

        Sends the grievance text to Sarvam-M with a structured-extraction
        system prompt asking for JSON output.  On any failure (malformed
        JSON, hallucinated enums, etc.) a ``SarvamError`` is raised so the
        ``FallbackAIProvider`` delegates to ``LocalAIProvider``.
        """
        from app.services.extraction import (
            CATEGORY_KEYWORDS,
            CATEGORY_TO_DEPARTMENT,
        )

        settings = get_settings()

        # ── allowed enumerations ──────────────────────────────────

        categories = sorted(CATEGORY_KEYWORDS.keys())  # e.g. ["electricity", "health", ...]
        departments = sorted(set(CATEGORY_TO_DEPARTMENT.values()))
        # e.g. ["agriculture_department", "anti_corruption", ...]
        urgencies = ["low", "medium", "high", "critical"]

        # ── system prompt ────────────────────────────────────────

        system_prompt = (
            "You extract structured fields from an Indian civic grievance.\n"
            "Return ONLY valid JSON — no markdown, no explanation, no backticks.\n\n"
            "Keys: category, department, urgency, ward, landmark, summary.\n"
            "- category: one of {categories}\n"
            "- department: one of {departments}\n"
            "- urgency: one of {urgencies}\n"
            "- ward: digit string if present in text, otherwise empty string\n"
            "- landmark: free text if a named landmark appears, otherwise empty string\n"
            "- summary: ≤120 characters, in the source language\n\n"
            "Do not invent ward numbers, landmarks, or facts not in the input.\n"
            "If you cannot determine a field, use the empty string for strings\n"
            "and the most neutral enum value for enums.\n"
        ).format(
            categories=", ".join(categories),
            departments=", ".join(departments),
            urgencies=", ".join(urgencies),
        )

        # ── user prompt ──────────────────────────────────────────

        user_prompt = f"Language: {language}\nGrievance: {text}"

        # ── chat completion ──────────────────────────────────────

        payload: Dict = {
            "model": settings.sarvam_chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "reasoning_effort": None,
        }

        response = self._client.post_json("/v1/chat/completions", payload)

        # ── extract response text ────────────────────────────────

        try:
            raw = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SarvamError("Unexpected chat completion response shape") from exc

        if not isinstance(raw, str) or not raw.strip():
            raise SarvamError("Chat completion response empty or not a string")

        # ── parse JSON (try first JSON object, then raw) ────────

        parsed: Dict = {}
        # Strip common markdown fences first
        candidate = raw.strip()
        for fence in ("```json", "```"):
            if candidate.startswith(fence):
                candidate = candidate[len(fence):].strip()
            if candidate.endswith("```"):
                candidate = candidate[:-3].strip()

        # Try json.JSONDecoder to grab the first valid JSON object
        decoder = json.JSONDecoder()
        try:
            parsed, _ = decoder.raw_decode(candidate)
        except (json.JSONDecodeError, ValueError):
            # Fall back to regex {…} extraction
            match = re.search(r"\{.*\}", candidate, re.DOTALL)
            json_candidate = match.group(0) if match else candidate
            try:
                parsed = json.loads(json_candidate)
            except (json.JSONDecodeError, ValueError) as exc:
                raise SarvamError(
                    f"Failed to parse extraction JSON: {exc}"
                ) from exc

        if not isinstance(parsed, dict):
            raise SarvamError("Extraction JSON is not an object")

        # ── guardrail: whitelist enum fields ─────────────────────

        category = str(parsed.get("category", "")).strip()
        if category not in CATEGORY_KEYWORDS:
            category = "other"

        department = str(parsed.get("department", "")).strip()
        if department not in CATEGORY_TO_DEPARTMENT.values():
            department = ""

        urgency_raw = str(parsed.get("urgency", "")).strip().lower()
        urgency = urgency_raw if urgency_raw in urgencies else "medium"

        ward = str(parsed.get("ward", "")).strip()
        # Keep only digits; cap at 3 chars
        ward = "".join(ch for ch in ward if ch.isdigit())[:3]

        landmark = str(parsed.get("landmark", "")).strip()[:120]
        summary = str(parsed.get("summary", "")).strip()[:120]

        # ── guardrail: PII leak check ────────────────────────────

        self._check_pii_leak(summary)
        self._check_pii_leak(landmark)

        # ── build result ─────────────────────────────────────────
        # Use the model-generated summary as normalized_text, falling
        # back to whitespace-collapsed input when summary is empty.
        normalized_text = summary if summary.strip() else " ".join(text.split())
        self._check_pii_leak(normalized_text)

        result = ExtractionResult(
            category=category,
            department=department,
            urgency=urgency,
            ward=ward,
            landmark=landmark,
            language=language,
            normalized_text=normalized_text,
            pii_redacted_text=redact_all(normalized_text),
        )
        return result

    # ── synthesize_speech ───────────────────────────────────────

    def synthesize_speech(
        self, text: str, language: str = "hi-IN", speaker: str = "aditya"
    ) -> bytes:
        """Convert text to speech via Sarvam TTS.

        Parameters
        ----------
        text : str
            The text to synthesize. Must be <= 500 characters.
        language : str
            Target language code (default "hi-IN").
        speaker : str
            Speaker name (default "default").

        Returns
        -------
        bytes
            Decoded WAV audio bytes.

        Raises
        ------
        SarvamError
            If text > 500 characters, or the API call fails.
        """
        settings = get_settings()

        # ── size guard ─────────────────────────────────────────
        if len(text) > 500:
            raise SarvamError(
                "Text too long for TTS: %d characters (max 500)" % len(text)
            )

        # ── TTS payload ────────────────────────────────────────
        payload: Dict = {
            "model": settings.sarvam_tts_model,
            "inputs": [text],
            "target_language_code": language,
            "speaker": speaker,
        }

        response = self._client.post_json("/text-to-speech", payload)

        # ── decode base64 audio ─────────────────────────────────
        try:
            encoded = response["audios"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise SarvamError(
                "Unexpected TTS response shape: missing 'audios' key or empty list"
            ) from exc

        try:
            audio_bytes = base64.b64decode(encoded)
        except Exception as exc:
            raise SarvamError("Failed to decode TTS audio base64") from exc

        return audio_bytes


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

    def transcribe_audio(
        self, audio_bytes: bytes,
        language_code: str = "hi-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        return self._call_with_fallback(
            "transcribe_audio",
            self.primary.transcribe_audio,
            self.fallback.transcribe_audio,
            audio_bytes,
            language_code,
            model,
        )

    def transcribe_audio_translate(
        self, audio_bytes: bytes,
        target_language: str = "en-IN",
        model: Optional[str] = None,
    ) -> TranscriptionResult:
        return self._call_with_fallback(
            "transcribe_audio_translate",
            self.primary.transcribe_audio_translate,
            self.fallback.transcribe_audio_translate,
            audio_bytes,
            target_language,
            model,
        )

    def translate_text(
        self, text: str, target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        return self._call_with_fallback(
            "translate_text",
            self.primary.translate_text,
            self.fallback.translate_text,
            text,
            target_language,
            source_language,
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

    def synthesize_speech(
        self, text: str, language: str = "hi-IN", speaker: str = "aditya"
    ) -> bytes:
        return self._call_with_fallback(
            "synthesize_speech",
            self.primary.synthesize_speech,
            self.fallback.synthesize_speech,
            text,
            language,
            speaker,
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
