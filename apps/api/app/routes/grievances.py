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
from app.services.redaction import redact_all
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
    if isinstance(x_ai_provider, str) and x_ai_provider:
        if settings.allow_provider_override:
            return _provider_from_name(x_ai_provider)
        # Don't silently ignore the header — otherwise an eval run with
        # `--provider sarvam` looks like it switched providers but actually
        # reused the server default, producing two identical-looking reports.
        logger.warning(
            "Ignoring X-AI-Provider=%s: ALLOW_PROVIDER_OVERRIDE is off. "
            "Set ALLOW_PROVIDER_OVERRIDE=true to honor per-request provider "
            "selection (needed for /evals local-vs-Sarvam comparisons).",
            x_ai_provider,
        )
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
        suburb=g.suburb,
        road=g.road,
        sector=g.sector,
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

def _locality_label(ward: str, area: str, location=None) -> str:
    """Best available administrative/locality anchor — ward or not.

    Indian civic geography is heterogeneous (ward / sector / zone / village),
    so fall back through the most specific data we actually have instead of
    assuming a ward. (``location.sector`` is a Nominatim district-level value,
    not an urban "Sector N"; capturing a true sector number is future work.)
    """
    if ward:
        return f"Ward {ward}"
    if location and location.suburb:
        return location.suburb
    if area:
        return area
    if location and location.sector:
        return location.sector
    if location and location.city:
        return location.city
    return ""


def _cluster_title(extraction, final_ward: str, area: str, location=None) -> str:
    """Issue + best locality anchor. Granular road/suburb/area are carried on
    the structured location fields (and shown in the UI), not piled into the
    title."""
    cat = extraction.category.replace("_", " ").title()
    label = _locality_label(final_ward, area, location)
    return f"{cat}, {label}" if label else cat

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
    title = _cluster_title(extraction, final_ward, area, location)
    # The cluster summary is published on the public dashboard. Redact it at
    # the source — normalized_text is the pivot-language clustering text and is
    # never otherwise run through redaction (H2). And when the citizen withheld
    # consent to public sharing, don't surface their words at all: keep the
    # aggregate cluster but fall back to a generic, location-based summary (H4).
    if grievance.consent_public:
        summary = redact_all(extraction.normalized_text) or title
    else:
        summary = title
    new_cluster = IssueCluster(
        title=title,
        summary=summary,
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


def _finalize_grievance(
    session: Session,
    extraction: ExtractionResult,
    *,
    user_id: str,
    raw_text: str,
    language: str,
    consent_public: bool,
    latitude: Optional[float],
    longitude: Optional[float],
    transcript_text: str = "",
    audio_key: Optional[str] = None,
) -> GrievanceResponse:
    """Shared tail for the text and audio grievance endpoints.

    Given an already-extracted (and pivot-translated) ``extraction``, infer
    ward/area/location from coords, embed once, find or create a cluster,
    persist the grievance, and build the response. The two endpoints differ
    only in how they obtain ``extraction`` and a few grievance fields
    (raw_text, transcript_text, language, audio_key).
    """
    from app.services.geocoding import (
        infer_area,
        infer_ward,
        resolve_location,
        ward_disagrees,
    )

    has_coords = latitude is not None and longitude is not None
    inferred_ward = infer_ward(latitude, longitude) if has_coords else None

    # Ward inference from coords (BEFORE clustering): fill a missing ward, or
    # log when the text-provided ward disagrees with the coordinates.
    final_ward = extraction.ward
    if has_coords:
        if not final_ward and inferred_ward:
            final_ward = inferred_ward
            extraction.ward = inferred_ward  # so clustering sees it
        elif final_ward and inferred_ward and ward_disagrees(final_ward, latitude, longitude):
            logger.warning(
                "Ward mismatch: text says %s but coords (%.4f, %.4f) are near ward %s",
                final_ward, latitude, longitude, inferred_ward,
            )

    area = infer_area(latitude, longitude) if has_coords else ""
    location = resolve_location(session, latitude, longitude) if has_coords else None

    # Suppress GPS-derived area/location when the text ward conflicts with coords.
    if final_ward and inferred_ward and ward_disagrees(final_ward, latitude, longitude):
        area = ""
        location = None

    # Compute the embedding once (shared between clustering and persistence).
    emb_json = embed_to_json(extraction.normalized_text)

    matched = find_matching_cluster(
        session, extraction,
        grievance_embedding_json=emb_json,
        grievance_lat=latitude,
        grievance_lon=longitude,
    )
    action = "join_cluster" if matched else "create_cluster"

    grievance = Grievance(
        user_id=user_id,
        raw_text=raw_text,
        transcript_text=transcript_text,
        normalized_text=extraction.normalized_text,
        language=language,
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

    cluster_id = None
    cluster_title = None

    if matched:
        grievance.cluster_id = matched.id
        grievance.status = "clustered"
        matched.grievance_count += 1
        # Update the centroid via incremental mean weighted by coordinate_count
        # (historical grievances without coords don't contribute to it).
        if has_coords:
            if matched.centroid_latitude is not None and matched.centroid_longitude is not None:
                n = matched.coordinate_count
                matched.centroid_latitude = (matched.centroid_latitude * n + latitude) / (n + 1)
                matched.centroid_longitude = (matched.centroid_longitude * n + longitude) / (n + 1)
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
        cluster_id, cluster_title = _create_cluster_for_grievance(
            session, extraction, final_ward, grievance, emb_json,
            latitude, longitude, area, location,
        )

    session.refresh(grievance)

    return GrievanceResponse(
        grievance=_grievance_to_read(grievance),
        extraction=extraction,
        matched_cluster_id=cluster_id if matched else None,
        matched_cluster_title=cluster_title if matched else None,
        suggested_action=action,
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

    return _finalize_grievance(
        session,
        extraction,
        user_id=body.user_id,
        raw_text=body.text,
        language=extraction.language,
        consent_public=body.consent_public,
        latitude=body.latitude,
        longitude=body.longitude,
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

    # 2. Read at most the cap (+1 byte) so an oversized upload is rejected
    #    without materializing an unbounded body in memory.
    audio_bytes = audio.file.read(_MAX_AUDIO_SIZE + 1)

    if len(audio_bytes) > _MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large (max {_MAX_AUDIO_SIZE} bytes / 10 MB)",
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

    # 5. Run the extraction pipeline on the English transcript.
    extraction: ExtractionResult = provider.extract_grievance(
        transcript, "en-IN"
    )

    return _finalize_grievance(
        session,
        extraction,
        user_id=user_id,
        raw_text=transcript,
        transcript_text=transcript,
        language=detected_language,
        consent_public=consent_public,
        latitude=latitude,
        longitude=longitude,
        audio_key=audio_key,
    )