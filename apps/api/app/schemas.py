from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel


# ── User ──────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    phone_number: str
    display_name: str = ""
    preferred_language: str = "hi"
    ward: str = ""


class UserRead(BaseModel):
    id: str
    phone_number: str
    display_name: str
    preferred_language: str
    ward: str
    created_at: datetime


# ── Grievance ─────────────────────────────────────────────────────────


class GrievanceCreate(BaseModel):
    user_id: str
    text: str = ""
    language: str = "hi-IN"
    consent_public: bool = True
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class GrievanceRead(BaseModel):
    id: str
    user_id: str
    raw_text: str
    transcript_text: str
    normalized_text: str
    language: str
    issue_category: str
    department: str
    urgency: str
    ward: str
    area: str = ""
    area_source: str = ""
    suburb: str = ""
    road: str = ""
    sector: str = ""
    landmark: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    pii_redacted_text: str
    cluster_id: Optional[str] = None
    status: str
    consent_public: bool
    audio_key: Optional[str] = None
    created_at: datetime


# ── Extraction ────────────────────────────────────────────────────────


class ExtractionResult(BaseModel):
    category: str = "other"
    department: str = ""
    urgency: str = "medium"
    ward: str = ""
    landmark: str = ""
    language: str = "hi"
    normalized_text: str = ""
    pii_redacted_text: str = ""


class GrievanceResponse(BaseModel):
    grievance: GrievanceRead
    extraction: ExtractionResult
    matched_cluster_id: Optional[str] = None
    matched_cluster_title: Optional[str] = None
    suggested_action: str = "create_cluster"  # "create_cluster" or "join_cluster"


# ── Cluster ───────────────────────────────────────────────────────────


class ClusterRead(BaseModel):
    id: str
    title: str
    summary: str
    issue_category: str
    department: str
    ward: str
    area: str = ""
    area_source: str = ""
    suburb: str = ""
    road: str = ""
    sector: str = ""
    landmark: str
    status: str
    support_count: int
    grievance_count: int
    urgency_score: float
    centroid_latitude: Optional[float] = None
    centroid_longitude: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class RedactedGrievanceSample(BaseModel):
    id: str
    language: str
    issue_category: str
    department: str
    urgency: str
    ward: str
    landmark: str
    pii_redacted_text: str
    status: str
    created_at: datetime


class ClusterDetail(ClusterRead):
    sample_grievances: list[RedactedGrievanceSample] = []


class ClusterSupportCreate(BaseModel):
    user_id: str
    grievance_id: str
    consent_to_file: bool = False


# ── ComplaintDraft ───────────────────────────────────────────────────


class ComplaintDraftRead(BaseModel):
    id: str
    cluster_id: str
    title: str
    body: str
    department: str
    language: str
    source_grievance_ids: str
    status: str
    created_at: datetime


# ── Eval ──────────────────────────────────────────────────────────────


class EvalPipelineInput(BaseModel):
    input_text: str
    language: str = "hi"


class EvalPipelineOutput(BaseModel):
    category: str
    department: str
    ward: str
    landmark: str
    urgency: str
    pii_redacted_text: str
    matched_cluster_id: Optional[str] = None


class EvalRunRead(BaseModel):
    id: str
    name: str
    total_cases: int
    passed_cases: int
    classification_accuracy: float
    routing_accuracy: float
    location_accuracy: float
    cluster_accuracy: float
    pii_redaction_accuracy: float
    draft_faithfulness: float
    p95_latency_ms: float
    created_at: datetime


# ── TTS ────────────────────────────────────────────────────────────────


class TTSRequest(BaseModel):
    text: str
    language: str = "hi-IN"
    speaker: str = "aditya"


# ── Transcription ────────────────────────────────────────────────────


@dataclass
class TranscriptionResult:
    """Result from audio transcription.

    Attributes
    ----------
    transcript : str
        The transcribed text.
    detected_language : str
        Language code detected by the STT engine.
    confidence : float
        Confidence score between 0.0 and 1.0.
    """
    transcript: str
    detected_language: str
    confidence: float