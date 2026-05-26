from typing import List, Optional

import logging

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlmodel import Session

from app.db import get_session
from app.models import Grievance, IssueCluster
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
        area=g.area,
        area_source=g.area_source,
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

def _cluster_title(extraction, final_ward: str, area: str, location=None) -> str:
    """Build a human-readable cluster title using available location data."""
    cat = extraction.category.replace("_", " ").title()

    # Prefer specific location markers
    loc = location
    if loc and loc.landmark:
        base = f"{cat} near {loc.landmark}"
    elif loc and loc.road:
        base = f"{cat} on {loc.road}"
    elif area:
        base = f"{cat} near {area}"
    else:
        base = cat

    # Add administrative context
    parts = [base]
    if loc and loc.suburb and loc.suburb != area:
        parts.append(loc.suburb)
    if final_ward:
        parts.append(f"Ward {final_ward}")
    return ", ".join(parts)

def _create_cluster_for_grievance(
    session: Session,
    extraction,
    final_ward: str,
    grievance,
    emb_json,
    lat, lon,
    area: str = "",
    location=None,
):
    """Auto-create an IssueCluster for an unmatched grievance and link it."""
    new_cluster = IssueCluster(
        title=_cluster_title(extraction, final_ward, area, location),
        summary=extraction.normalized_text,
        issue_category=extraction.category,
        department=extraction.department,
        ward=final_ward,
        status="open",
        grievance_count=1,
        support_count=0,
        urgency_score={"high": 0.85, "medium": 0.55, "low": 0.25}.get(extraction.urgency, 0.5),
        centroid_latitude=lat,
        centroid_longitude=lon,
        coordinate_count=1 if (lat is not None and lon is not None) else 0,
        area=location.area if location else area,
        area_source=location.source if location else ("demo_mumbai" if area else ""),
        suburb=location.suburb if location else "",
        road=location.road if location else "",
        sector=location.sector if location else "",
        location_json=location.raw_json if location else None,
    )
    # Initialize embedding so subsequent submissions can match
    if emb_json is not None:
        new_cluster.centroid_embedding_json = emb_json
        new_cluster.embedding_count = 1

    # Add cluster first so its ID exists before grievance references it
    try:
        session.add(new_cluster)
        session.flush()
        grievance.cluster_id = new_cluster.id
        grievance.status = "clustered"
        session.add(grievance)
        session.commit()
        session.refresh(new_cluster)
        return new_cluster.id, new_cluster.title
    except Exception:
        session.rollback()
        raise


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
    from app.services.geocoding import infer_area, infer_ward, resolve_location, ward_disagrees as _ward_disagrees

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
            area = ""  # suppress GPS area when ward sources conflict

    area = infer_area(body.latitude, body.longitude) if body.latitude is not None and body.longitude is not None else ""
    location = resolve_location(session, body.latitude, body.longitude) if body.latitude is not None and body.longitude is not None else None

    # Compute embedding once (shared between clustering and persistence)
    emb_json = embed_to_json(extraction.normalized_text)

    # Check for matching cluster
    matched = find_matching_cluster(
        session, extraction,
        grievance_embedding_json=emb_json,
        grievance_lat=body.latitude,
        grievance_lon=body.longitude,
    )
    action = "join_cluster" if matched else "create_cluster"

    # Create grievance object (NOT committed yet — cluster decision first)
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
        area=location.area if location else area,
        area_source=location.source if location else ("demo_mumbai" if area else ""),
        suburb=location.suburb if location else "",
        road=location.road if location else "",
        sector=location.sector if location else "",
        location_json=location.raw_json if location else None,
        consent_public=body.consent_public,
        embedding_json=emb_json,
    )

    # Update cluster if joined
    cluster_id = None
    cluster_title = None

    if matched:
        grievance.cluster_id = matched.id
        grievance.status = "clustered"
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
        session.add_all([grievance, matched])
        session.commit()
        cluster_id = matched.id
        cluster_title = matched.title
    else:
        # Create cluster AND grievance in one transaction via shared helper
        cluster_id, cluster_title = _create_cluster_for_grievance(
            session, extraction, final_ward, grievance, emb_json,
            body.latitude, body.longitude, area, location,
        )

    session.refresh(grievance)

    return GrievanceResponse(
        grievance=_grievance_to_read(grievance),
        extraction=extraction,
        matched_cluster_id=cluster_id,
        matched_cluster_title=cluster_title,
        suggested_action=action,
    )


@router.get("", response_model=List[GrievanceRead])
def list_grievances(
    user_id: str = Query(..., description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> List[GrievanceRead]:
    grievances = (
        session.query(Grievance)
        .filter(Grievance.user_id == user_id)
        .order_by(Grievance.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_grievance_to_read(g) for g in grievances]


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
    from app.services.geocoding import infer_area, infer_ward, resolve_location, ward_disagrees as _ward_disagrees

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
            area = ""  # suppress GPS area when ward sources conflict

    area = infer_area(latitude, longitude) if latitude is not None and longitude is not None else ""
    location = resolve_location(session, latitude, longitude) if latitude is not None and longitude is not None else None

    # Compute embedding once (shared between clustering and persistence)
    emb_json = embed_to_json(extraction.normalized_text)

    # 6. Check for matching cluster
    matched = find_matching_cluster(
        session, extraction,
        grievance_embedding_json=emb_json,
        grievance_lat=latitude,
        grievance_lon=longitude,
    )
    action = "join_cluster" if matched else "create_cluster"

    # 7. Create grievance object (NOT committed yet — cluster decision first)
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
        area=location.area if location else area,
        area_source=location.source if location else ("demo_mumbai" if area else ""),
        suburb=location.suburb if location else "",
        road=location.road if location else "",
        sector=location.sector if location else "",
        location_json=location.raw_json if location else None,
        consent_public=consent_public,
        audio_key=audio_key,
        embedding_json=emb_json,
    )

    # Update cluster if joined — centroid + coordinate_count
    cluster_id = None
    cluster_title = None

    if matched:
        grievance.cluster_id = matched.id
        grievance.status = "clustered"
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
        session.add_all([grievance, matched])
        session.commit()
        cluster_id = matched.id
        cluster_title = matched.title
    else:
        # Create cluster AND grievance in one transaction via shared helper
        cluster_id, cluster_title = _create_cluster_for_grievance(
            session, extraction, final_ward, grievance, emb_json,
            latitude, longitude, area, location,
        )

    session.refresh(grievance)

    return GrievanceResponse(
        grievance=_grievance_to_read(grievance),
        extraction=extraction,
        matched_cluster_id=cluster_id,
        matched_cluster_title=cluster_title,
        suggested_action=action,
    )