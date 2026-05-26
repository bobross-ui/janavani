import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── User ──────────────────────────────────────────────────────────────


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    phone_number: str = Field(index=True)
    display_name: str = Field(default="")
    preferred_language: str = Field(default="hi")
    ward: str = Field(default="")
    created_at: datetime = Field(default_factory=_now)


# ── Grievance ─────────────────────────────────────────────────────────


class Grievance(SQLModel, table=True):
    __tablename__ = "grievances"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    raw_text: str = Field(default="")
    transcript_text: str = Field(default="")
    normalized_text: str = Field(default="")
    language: str = Field(default="hi")
    issue_category: str = Field(default="other", index=True)
    department: str = Field(default="")
    urgency: str = Field(default="medium")
    ward: str = Field(default="", index=True)
    landmark: str = Field(default="")
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    pii_redacted_text: str = Field(default="")
    cluster_id: Optional[str] = Field(default=None, foreign_key="issue_clusters.id")
    status: str = Field(default="submitted", index=True)
    consent_public: bool = Field(default=True)
    audio_key: Optional[str] = Field(default=None)
    # JSON-serialised embedding vector (list of floats).  Stored as
    # text so it works on both SQLite (tests) and Postgres (prod).
    embedding_json: Optional[str] = Field(default=None)
    area: str = Field(default="")
    area_source: str = Field(default="")
    suburb: str = Field(default="")
    road: str = Field(default="")
    landmark: str = Field(default="")
    sector: str = Field(default="")
    location_json: Optional[str] = Field(default=None)  # raw reverse-geocode result
    created_at: datetime = Field(default_factory=_now)


# ── IssueCluster ──────────────────────────────────────────────────────


class IssueCluster(SQLModel, table=True):
    __tablename__ = "issue_clusters"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    title: str = Field(default="")
    summary: str = Field(default="")
    issue_category: str = Field(default="other", index=True)
    department: str = Field(default="")
    ward: str = Field(default="", index=True)
    area: str = Field(default="")
    area_source: str = Field(default="")
    suburb: str = Field(default="")
    road: str = Field(default="")
    sector: str = Field(default="")
    location_json: Optional[str] = Field(default=None)
    landmark: str = Field(default="")
    status: str = Field(default="open", index=True)
    support_count: int = Field(default=0)
    grievance_count: int = Field(default=0)
    urgency_score: float = Field(default=0.0)
    centroid_latitude: Optional[float] = Field(default=None)
    centroid_longitude: Optional[float] = Field(default=None)
    coordinate_count: int = Field(default=0)
    # JSON-serialised centroid embedding (list of floats).
    centroid_embedding_json: Optional[str] = Field(default=None)
    # Number of grievance embeddings that have contributed to the centroid.
    embedding_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ── ClusterSupport ────────────────────────────────────────────────────


class ClusterSupport(SQLModel, table=True):
    __tablename__ = "cluster_supports"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    cluster_id: str = Field(foreign_key="issue_clusters.id", index=True)
    user_id: str = Field(foreign_key="users.id")
    grievance_id: str = Field(foreign_key="grievances.id")
    consent_to_file: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now)


# ── ComplaintDraft ────────────────────────────────────────────────────


class ComplaintDraft(SQLModel, table=True):
    __tablename__ = "complaint_drafts"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    cluster_id: str = Field(foreign_key="issue_clusters.id", index=True)
    title: str = Field(default="")
    body: str = Field(default="")
    department: str = Field(default="")
    language: str = Field(default="hi")
    source_grievance_ids: str = Field(default="")  # JSON list stored as string
    status: str = Field(default="draft")
    created_at: datetime = Field(default_factory=_now)


# ── EvalRun ───────────────────────────────────────────────────────────


class EvalRun(SQLModel, table=True):
    __tablename__ = "eval_runs"

    id: str = Field(default_factory=_new_uuid, primary_key=True)
    name: str = Field(default="")
    total_cases: int = Field(default=0)
    passed_cases: int = Field(default=0)
    classification_accuracy: float = Field(default=0.0)
    routing_accuracy: float = Field(default=0.0)
    location_accuracy: float = Field(default=0.0)
    cluster_accuracy: float = Field(default=0.0)
    pii_redaction_accuracy: float = Field(default=0.0)
    draft_faithfulness: float = Field(default=0.0)
    p95_latency_ms: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=_now)