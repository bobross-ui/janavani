"""Eval pipeline route — end-to-end evaluation without persisting."""

import json
import logging
import time
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.services.ai_provider import AIProvider
from app.services.clustering import find_matching_cluster
from app.services.embeddings import embed_to_json
from app.services.redaction import redact_all
from app.routes.grievances import get_request_ai_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evals", tags=["evals"])


# ── Report path (resolved from config/cwd once at startup) ──────────

_EVAL_REPORT_PATH: Optional[Path] = None


def _resolve_report_path() -> Path:
    """Resolve the eval report path from settings or a sensible default.

    Uses a configurable path if set, otherwise falls back to
    {cwd}/data/eval_reports/latest.json.  Callers that need to
    override the location can set ``EVAL_REPORT_PATH`` in .env.
    """
    settings = get_settings()
    custom = getattr(settings, "eval_report_path", None)
    if custom:
        return Path(custom)
    # Default: relative to cwd (works for local dev; Docker maps a volume)
    return Path("data/eval_reports/latest.json")


def _get_report_path() -> Path:
    global _EVAL_REPORT_PATH
    if _EVAL_REPORT_PATH is None:
        _EVAL_REPORT_PATH = _resolve_report_path()
    return _EVAL_REPORT_PATH


# ── Request / Response models ────────────────────────────────────────

class PipelineRequest(BaseModel):
    input_text: str
    language: str = "hi-IN"


class LatencyBreakdown(BaseModel):
    extract_ms: float = 0.0
    redact_ms: float = 0.0
    translate_ms: float = 0.0
    cluster_match_ms: float = 0.0
    total_ms: float = 0.0


class PipelineResult(BaseModel):
    category: str = "other"
    department: str = ""
    urgency: str = "medium"
    ward: str = ""
    landmark: str = ""
    pii_redacted_text: str = ""
    matched_cluster_id: Optional[str] = None
    matched_cluster_title: Optional[str] = None
    latency: LatencyBreakdown


# ── Pipeline endpoint ────────────────────────────────────────────────

@router.post("/pipeline", response_model=PipelineResult)
def run_pipeline(
    body: PipelineRequest,
    provider: AIProvider = Depends(get_request_ai_provider),
    session: Session = Depends(get_session),
) -> PipelineResult:
    """Run extract → redact → translate → cluster-match without persisting.

    Used by bhasha-test --target mode to evaluate the full pipeline against
    a live API without polluting the demo database.
    """
    settings = get_settings()
    t0 = time.perf_counter()

    # 1. Extract structured fields
    t1 = time.perf_counter()
    extraction = provider.extract_grievance(body.input_text, body.language)
    extract_ms = (time.perf_counter() - t1) * 1000

    # 2. Redact PII
    t2 = time.perf_counter()
    pii_redacted = redact_all(extraction.normalized_text)
    redact_ms = (time.perf_counter() - t2) * 1000

    # 3. Translate to pivot language — use a copy so we don't mutate the
    #    original extraction object (which may be shared or immutable).
    t3 = time.perf_counter()
    pivot_language = settings.clustering_pivot_language
    normalized = extraction.normalized_text
    if extraction.language and extraction.language != pivot_language and normalized:
        normalized = provider.translate_text(
            normalized, pivot_language, source_language=extraction.language
        )
    translate_ms = (time.perf_counter() - t3) * 1000

    # Build a clustering extraction with the translated normalized_text
    clustering_extraction = extraction.model_copy(
        update={"normalized_text": normalized}
    )

    # 4. Cluster match (in-memory read, no persist)
    t4 = time.perf_counter()
    emb_json = embed_to_json(clustering_extraction.normalized_text)
    matched = find_matching_cluster(
        session, clustering_extraction,
        grievance_embedding_json=emb_json,
    )
    cluster_match_ms = (time.perf_counter() - t4) * 1000

    total_ms = (time.perf_counter() - t0) * 1000

    return PipelineResult(
        category=extraction.category,
        department=extraction.department,
        urgency=extraction.urgency,
        ward=extraction.ward,
        landmark=extraction.landmark,
        pii_redacted_text=pii_redacted,
        matched_cluster_id=matched.id if matched else None,
        matched_cluster_title=matched.title if matched else None,
        latency=LatencyBreakdown(
            extract_ms=extract_ms,
            redact_ms=redact_ms,
            translate_ms=translate_ms,
            cluster_match_ms=cluster_match_ms,
            total_ms=total_ms,
        ),
    )


# ── Report retrieval ─────────────────────────────────────────────────

@router.get("/latest")
def get_latest_report() -> JSONResponse:
    """Return the most recent eval report.

    The report is written by the bhasha-test CLI with --output pointing to
    data/eval_reports/latest.json. Returns 404 if no report exists yet,
    503 if the report file is malformed.
    """
    return _serve_report(_get_report_path(), "latest")


@router.get("/compare")
def get_comparison() -> JSONResponse:
    """Return local and Sarvam eval reports side by side for comparison."""
    latest_path = _get_report_path()
    sarvam_path = latest_path.parent / "sarvam.json"

    local = _load_report(latest_path, "latest")
    sarvam = _load_report(sarvam_path, "sarvam")

    return JSONResponse(content={"local": local, "sarvam": sarvam})


def _load_report(path: Path, label: str) -> Optional[dict]:
    """Load a single report, returning None if missing (don't 404 the whole comparison)."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        logger.warning("Malformed eval report at %s (%s): %s", label, path, exc)
        return None


def _serve_report(report_path: Path, label: str) -> JSONResponse:
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "No eval report yet. Run: bhasha-test evaluate "
                "data/eval_cases/grievance_cases.yaml "
                "--target http://localhost:8000 "
                "--output data/eval_reports/latest.json"
            ),
        )
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        logger.warning("Malformed eval report at %s: %s", report_path, exc)
        raise HTTPException(
            status_code=503,
            detail="Eval report is malformed. Re-run the evaluation to regenerate it.",
        ) from exc
    return JSONResponse(content=data)
