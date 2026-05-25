"""Eval pipeline route — end-to-end evaluation without persisting."""

import json
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.services.ai_provider import AIProvider
from app.services.clustering import find_matching_cluster
from app.services.redaction import redact_all
from app.routes.grievances import get_request_ai_provider

router = APIRouter(prefix="/evals", tags=["evals"])


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

    # 3. Translate to pivot language for cross-language clustering
    t3 = time.perf_counter()
    pivot_language = settings.clustering_pivot_language
    normalized = extraction.normalized_text
    if extraction.language and extraction.language != pivot_language and normalized:
        normalized = provider.translate_text(
            normalized, pivot_language, source_language=extraction.language
        )
        extraction.normalized_text = normalized
    translate_ms = (time.perf_counter() - t3) * 1000

    # 4. Cluster match (in-memory read, no persist)
    t4 = time.perf_counter()
    matched = find_matching_cluster(session, extraction)
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


# ── Report storage / retrieval ──────────────────────────────────────

_EVAL_REPORT_DIR = Path("data/eval_reports")
_LATEST_REPORT_PATH = _EVAL_REPORT_DIR / "latest.json"


def save_latest_report(report: dict[str, Any]) -> None:
    """Persist an eval report to data/eval_reports/latest.json."""
    _EVAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _LATEST_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/latest")
def get_latest_report() -> JSONResponse:
    """Return the most recent eval report.

    The report is written by the bhasha-test CLI with --output pointing to
    data/eval_reports/latest.json. Returns 404 if no report exists yet.
    """
    if not _LATEST_REPORT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="No eval report yet. Run bhasha-test evaluate --output data/eval_reports/latest.json",
        )
    data = json.loads(_LATEST_REPORT_PATH.read_text(encoding="utf-8"))
    return JSONResponse(content=data)
