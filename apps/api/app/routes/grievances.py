from typing import Optional

import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
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
from app.services.audio_storage import AudioStorage
from app.services.clustering import find_matching_cluster, update_cluster_embedding
from app.services.embeddings import embed_to_json
from app.services.sarvam_client import SarvamError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grievances", tags=["grievances"])


def _provider_from_name(provider_name: str) -> AIProvider:
    normalized = provider_name.strip().lower()
    if normalized == "local":
        return LocalAIProvider()
    if normalized == "sarvam":
        return get_ai_provider()  # returns FallbackAIProvider(Sarvam, Local) when key is set
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


def get_audio_storage() -> AudioStorage:
    return AudioStorage()


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
        audio_key=g.audio_key,
        created_at=g.created_at,
    )


@router.post("", response_model=GrievanceResponse)
def submit_grievance(
    body: GrievanceCreate,
    provider: AIProvider = Depends(get_request_ai_provider),
    session: Session = Depends(get_session),
) -> GrievanceResponse:
    settings = get_settings()

    # Extract structured fields
    extraction: ExtractionResult = provider.extract_grievance(
        body.text, body.language
    )

    # Translate to pivot language for cross-language clustering
    pivot_language = settings.clustering_pivot_language
    if (
        extraction.language
        and extraction.language != pivot_language
        and extraction.normalized_text
    ):
        extraction.normalized_text = provider.translate_text(
            extraction.normalized_text,
            pivot_language,
            source_language=extraction.language,
        )

    # ── Ward inference from coords (BEFORE clustering) ──────────
    # When GPS coords are available, infer ward if extraction missed it.
    # Must run before find_matching_cluster so the inferred ward feeds
    # into area matching and haversine decisions.
    from app.services.geocoding import infer_ward, ward_disagrees as _ward_disagrees

    final_ward = extraction.ward
    if body.latitude is not None and body.longitude is not None:
        inferred = infer_ward(body.latitude, body.longitude)
        if not final_ward and inferred:
            final_ward = inferred
            extraction.ward = inferred  # so clustering sees it
        elif final_ward and inferred and _ward_disagrees(final_ward, body.latitude, body.longitude):
            logger.warning(
                "Ward mismatch: text says %s but coords (%.4f, %.4f) are near ward %s",
                final_ward, body.latitude, body.longitude, inferred,
            )

    # Check for matching cluster
    matched = find_matching_cluster(
        session, extraction,
        grievance_lat=body.latitude,
        grievance_lon=body.longitude,
    )
    action = "join_cluster" if matched else "create_cluster"

    # Create grievance record
    emb_json = embed_to_json(extraction.normalized_text)
    grievance = Grievance(
        user_id=body.user_id,
        raw_text=body.text,
        normalized_text=extraction.normalized_text,
        language=extraction.language,
        issue_category=extraction.category,
        department=extraction.department,
        urgency=extraction.urgency,
        ward=final_ward,
        landmark=extraction.landmark,
        latitude=body.latitude,
        longitude=body.longitude,
        pii_redacted_text=extraction.pii_redacted_text,
        cluster_id=matched.id if matched else None,
        consent_public=body.consent_public,
        embedding_json=emb_json,
    )
    session.add(grievance)
    session.commit()
    session.refresh(grievance)

    # Update cluster if joined
    if matched:
        matched.grievance_count += 1
        # Update cluster centroid using incremental mean weighted by
        # coordinate_count (not grievance_count — historical grievances
        # without coords don't contribute to centroid).
        if body.latitude is not None and body.longitude is not None:
            if matched.centroid_latitude is not None and matched.centroid_longitude is not None:
                n = matched.coordinate_count
                matched.centroid_latitude = (
                    (matched.centroid_latitude * n + body.latitude) / (n + 1)
                )
                matched.centroid_longitude = (
                    (matched.centroid_longitude * n + body.longitude) / (n + 1)
                )
            else:
                matched.centroid_latitude = body.latitude
                matched.centroid_longitude = body.longitude
            matched.coordinate_count += 1
        # Update centroid embedding (uses coordinate_count for weight)
        update_cluster_embedding(matched, emb_json)
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


# ── Audio submission endpoint ──────────────────────────────────────────

_MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_AUDIO_MIME_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mp3", "audio/mpeg",
    "audio/mp4", "audio/m4a", "audio/x-m4a",
}


@router.post("/audio", response_model=GrievanceResponse)
def submit_audio_grievance(
    audio: UploadFile = File(...),
    user_id: str = Form(...),
    language: str = Form(default=""),
    consent_public: bool = Form(default=True),
    latitude: Optional[float] = Form(default=None),
    longitude: Optional[float] = Form(default=None),
    provider: AIProvider = Depends(get_request_ai_provider),
    storage: AudioStorage = Depends(get_audio_storage),
    session: Session = Depends(get_session),
) -> GrievanceResponse:
    # 1. Validate audio
    if audio.content_type not in _ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {audio.content_type}. "
                   f"Allowed: {', '.join(sorted(_ALLOWED_AUDIO_MIME_TYPES))}",
        )

    # 2. Read bytes from UploadFile
    audio_bytes = audio.file.read()

    if len(audio_bytes) > _MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large: {len(audio_bytes)} bytes "
                   f"(max {_MAX_AUDIO_SIZE} bytes / 10 MB)",
        )

    # 3. Persist via AudioStorage.save_audio → audio_key
    audio_key = storage.save_audio(audio_bytes, audio.content_type)

    # 4. Call provider.transcribe_audio_translate → English transcript.
    # Sarvam's STT-translate endpoint auto-detects the spoken language, so the
    # mobile voice path does not need a pre-recording language picker.
    try:
        transcription = provider.transcribe_audio_translate(audio_bytes)
    except SarvamError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Speech-to-text translation failed: {exc}",
        )

    transcript = transcription.transcript
    detected_language = transcription.detected_language or "unknown"

    # 5. Run existing extraction pipeline on the English transcript returned by
    # 5. Run existing extraction pipeline on the English transcript.
    extraction: ExtractionResult = provider.extract_grievance(
        transcript, "en-IN"
    )

    # ── Ward inference from coords (BEFORE clustering) ──────────
    from app.services.geocoding import infer_ward, ward_disagrees as _ward_disagrees

    final_ward = extraction.ward
    if latitude is not None and longitude is not None:
        inferred = infer_ward(latitude, longitude)
        if not final_ward and inferred:
            final_ward = inferred
            extraction.ward = inferred
        elif final_ward and inferred and _ward_disagrees(final_ward, latitude, longitude):
            logger.warning(
                "Ward mismatch: text says %s but coords (%.4f, %.4f) are near ward %s",
                final_ward, latitude, longitude, inferred,
            )

    # 6. Check for matching cluster
    matched = find_matching_cluster(
        session, extraction,
        grievance_lat=latitude,
        grievance_lon=longitude,
    )
    action = "join_cluster" if matched else "create_cluster"

    # 7. Persist Grievance
    emb_json = embed_to_json(extraction.normalized_text)
    grievance = Grievance(
        user_id=user_id,
        raw_text=transcript,
        transcript_text=transcript,
        normalized_text=extraction.normalized_text,
        language=detected_language,
        issue_category=extraction.category,
        department=extraction.department,
        urgency=extraction.urgency,
        ward=final_ward,
        landmark=extraction.landmark,
        latitude=latitude,
        longitude=longitude,
        pii_redacted_text=extraction.pii_redacted_text,
        cluster_id=matched.id if matched else None,
        consent_public=consent_public,
        audio_key=audio_key,
        embedding_json=emb_json,
    )
    session.add(grievance)
    session.commit()
    session.refresh(grievance)

    # Update cluster if joined — centroid + coordinate_count
    if matched:
        matched.grievance_count += 1
        if latitude is not None and longitude is not None:
            if matched.centroid_latitude is not None and matched.centroid_longitude is not None:
                n = matched.coordinate_count
                matched.centroid_latitude = (
                    (matched.centroid_latitude * n + latitude) / (n + 1)
                )
                matched.centroid_longitude = (
                    (matched.centroid_longitude * n + longitude) / (n + 1)
                )
            else:
                matched.centroid_latitude = latitude
                matched.centroid_longitude = longitude
            matched.coordinate_count += 1
        update_cluster_embedding(matched, emb_json)
        session.add(matched)
        session.commit()

    return GrievanceResponse(
        grievance=_grievance_to_read(grievance),
        extraction=extraction,
        matched_cluster_id=matched.id if matched else None,
        matched_cluster_title=matched.title if matched else None,
        suggested_action=action,
    )
