from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models import Grievance
from app.schemas import (
    ExtractionResult,
    GrievanceCreate,
    GrievanceRead,
    GrievanceResponse,
)
from app.config import get_settings
from app.services.ai_provider import (
    AIProvider,
    LocalAIProvider,
    get_ai_provider,
)
from app.services.clustering import find_matching_cluster

router = APIRouter(prefix="/grievances", tags=["grievances"])


def _provider_from_name(provider_name: str) -> AIProvider:
    normalized = provider_name.strip().lower()
    if normalized == "local":
        return LocalAIProvider()
    if normalized == "sarvam":
        raise HTTPException(
            status_code=503,
            detail="Sarvam provider override is not available yet",
        )
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported AI provider override: {provider_name}",
    )


def get_request_ai_provider(
    x_ai_provider: Optional[str] = Header(default=None, alias="X-AI-Provider")
) -> AIProvider:
    settings = get_settings()
    if settings.allow_provider_override and isinstance(x_ai_provider, str) and x_ai_provider:
        return _provider_from_name(x_ai_provider)
    return get_ai_provider()


def _grievance_to_read(g: Grievance) -> GrievanceRead:
    return GrievanceRead(
        id=g.id,
        user_id=g.user_id,
        raw_text=g.raw_text,
        transcript_text=g.transcript_text,
        normalized_text=g.normalized_text,
        language=g.language,
        issue_category=g.issue_category,
        department=g.department,
        urgency=g.urgency,
        ward=g.ward,
        landmark=g.landmark,
        latitude=g.latitude,
        longitude=g.longitude,
        pii_redacted_text=g.pii_redacted_text,
        cluster_id=g.cluster_id,
        status=g.status,
        consent_public=g.consent_public,
        created_at=g.created_at,
    )


@router.post("", response_model=GrievanceResponse)
def submit_grievance(
    body: GrievanceCreate,
    provider: AIProvider = Depends(get_request_ai_provider),
    session: Session = Depends(get_session),
) -> GrievanceResponse:
    # Extract structured fields
    extraction: ExtractionResult = provider.extract_grievance(
        body.text, body.language
    )

    # Check for matching cluster
    matched = find_matching_cluster(session, extraction)
    action = "join_cluster" if matched else "create_cluster"

    # Create grievance record
    grievance = Grievance(
        user_id=body.user_id,
        raw_text=body.text,
        normalized_text=extraction.normalized_text,
        language=extraction.language,
        issue_category=extraction.category,
        department=extraction.department,
        urgency=extraction.urgency,
        ward=extraction.ward,
        landmark=extraction.landmark,
        latitude=body.latitude,
        longitude=body.longitude,
        pii_redacted_text=extraction.pii_redacted_text,
        cluster_id=matched.id if matched else None,
        consent_public=body.consent_public,
    )
    session.add(grievance)
    session.commit()
    session.refresh(grievance)

    # Update cluster if joined
    if matched:
        matched.grievance_count += 1
        session.add(matched)
        session.commit()

    return GrievanceResponse(
        grievance=_grievance_to_read(grievance),
        extraction=extraction,
        matched_cluster_id=matched.id if matched else None,
        matched_cluster_title=matched.title if matched else None,
        suggested_action=action,
    )


@router.get("/{grievance_id}", response_model=GrievanceRead)
def get_grievance(
    grievance_id: str, session: Session = Depends(get_session)
) -> GrievanceRead:
    grievance = session.get(Grievance, grievance_id)
    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")
    return _grievance_to_read(grievance)
