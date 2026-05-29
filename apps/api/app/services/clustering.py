"""Hybrid clustering — cosine similarity on embeddings with Jaccard fallback."""

import json
from typing import Optional

from sqlmodel import Session, select

from app.models import IssueCluster
from app.schemas import ExtractionResult
from app.services.embeddings import (
    cosine_similarity,
    parse_embedding_json,
    update_centroid,
)
from app.services.geocoding import haversine_m


def _token_overlap(text_a: str, text_b: str) -> float:
    """Jaccard token overlap between two strings."""
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _same_area(
    extraction_ward: str,
    extraction_lat: Optional[float],
    extraction_lon: Optional[float],
    cluster: IssueCluster,
    haversine_threshold_m: float = 300.0,
) -> bool:
    """Check whether a grievance and cluster are in the same area."""
    # Same ward — strongest signal
    if extraction_ward and cluster.ward and extraction_ward.strip() == cluster.ward.strip():
        return True

    # Haversine proximity
    if (
        extraction_lat is not None and extraction_lon is not None
        and cluster.centroid_latitude is not None
        and cluster.centroid_longitude is not None
    ):
        dist = haversine_m(
            extraction_lat, extraction_lon,
            cluster.centroid_latitude, cluster.centroid_longitude,
        )
        if dist <= haversine_threshold_m:
            return True

    # No ward AND no coords: can't determine area — allow semantic match
    # (caller uses stronger threshold via _token_overlap / cosine)
    if not extraction_ward and extraction_lat is None and extraction_lon is None:
        return True

    return False


def find_matching_cluster(
    session: Session,
    extraction: ExtractionResult,
    grievance_embedding_json: Optional[str] = None,
    similarity_threshold: float = 0.15,
    cosine_threshold: float = 0.78,
    haversine_threshold_m: float = 300.0,
    grievance_lat: Optional[float] = None,
    grievance_lon: Optional[float] = None,
) -> Optional[IssueCluster]:
    """Find the best matching cluster for a grievance.

    Match conditions:
    - Same issue category (hard filter)
    - Same area: ward match or haversine ≤ threshold
    - Semantic similarity: cosine ≥ τ when both sides have embeddings,
      Jaccard token overlap ≥ τ otherwise
    - Cluster status: open or drafted

    Uses the grievance embedding passed in (computed once by the caller)
    to avoid redundant model inference.
    """
    has_coords = grievance_lat is not None and grievance_lon is not None
    ward = (extraction.ward or "").strip()
    has_ward = bool(ward)

    if has_coords:
        # GPS available: filter by category + status, use haversine for area
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )
    elif has_ward:
        # Ward available but no GPS: filter by category + ward + status
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.ward == ward)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )
    else:
        # No ward AND no GPS: filter by category + status only,
        # rely entirely on semantic similarity with stricter thresholds.
        # _same_area allows through (no location data to check).
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )

    candidates = session.exec(statement).all()

    grievance_embedding = parse_embedding_json(grievance_embedding_json)
    best_match: Optional[IssueCluster] = None
    best_score = -1.0

    for cluster in candidates:
        if not _same_area(
            ward,
            grievance_lat, grievance_lon,
            cluster,
            haversine_threshold_m,
        ):
            continue

        cluster_embedding = parse_embedding_json(cluster.centroid_embedding_json)

        if grievance_embedding is not None and cluster_embedding is not None:
            score = cosine_similarity(grievance_embedding, cluster_embedding)
            # Stricter threshold when no location data available
            threshold = 0.88 if (not has_ward and not has_coords) else cosine_threshold
        else:
            # Jaccard fallback: at least one side lacks embeddings
            if cluster.summary:
                score = _token_overlap(extraction.normalized_text, cluster.summary)
            else:
                score = _token_overlap(extraction.normalized_text, cluster.title)
            # Stricter threshold when no location data available
            threshold = 0.35 if (not has_ward and not has_coords) else similarity_threshold

        if score >= threshold and score > best_score:
            best_score = score
            best_match = cluster

    return best_match


def update_cluster_embedding(
    cluster: IssueCluster,
    grievance_embedding_json: Optional[str],
) -> None:
    """Update the cluster centroid embedding when a grievance joins.

    Uses embedding_count for correct incremental mean weighting.
    On the first contribution, the centroid is set directly from the
    grievance embedding (no mean needed).
    """
    if not grievance_embedding_json:
        return
    new_vec = parse_embedding_json(grievance_embedding_json)
    if new_vec is None:
        return

    current_vec = parse_embedding_json(cluster.centroid_embedding_json)

    if current_vec is None:
        # First embedding — set directly
        cluster.centroid_embedding_json = grievance_embedding_json
        cluster.embedding_count = 1
    else:
        # Incremental mean.  Guard against legacy clusters whose
        # embedding_count was backfilled as 0 despite having a centroid.
        n = cluster.embedding_count
        if n <= 0:
            n = 1
        updated = update_centroid(current_vec, new_vec, n)
        cluster.centroid_embedding_json = json.dumps(updated)
        cluster.embedding_count = n + 1
