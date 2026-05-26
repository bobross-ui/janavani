"""Hybrid clustering — cosine similarity on embeddings with Jaccard fallback."""

from typing import Optional

from sqlmodel import Session, select

from app.models import IssueCluster
from app.schemas import ExtractionResult
from app.services.embeddings import (
    cosine_similarity,
    embed_to_json,
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
    if extraction_ward and cluster.ward and extraction_ward == cluster.ward:
        return True

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

    return False


def _score_candidate(
    extraction: ExtractionResult,
    cluster: IssueCluster,
    embedding: Optional[list[float]],
) -> float:
    """Score a cluster candidate against a grievance.

    Uses cosine similarity on embeddings when available; falls back to
    Jaccard token overlap otherwise (e.g., AI_PROVIDER=local without
    sentence-transformers installed).
    """
    cluster_embedding = parse_embedding_json(cluster.centroid_embedding_json)

    if embedding is not None and cluster_embedding is not None:
        return cosine_similarity(embedding, cluster_embedding)

    # Fallback: Jaccard token overlap
    if cluster.summary:
        return _token_overlap(extraction.normalized_text, cluster.summary)
    return _token_overlap(extraction.normalized_text, cluster.title)


def find_matching_cluster(
    session: Session,
    extraction: ExtractionResult,
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
    - Semantic similarity: cosine ≥ τ on embeddings, or
      Jaccard token overlap ≥ τ when embeddings unavailable
    - Cluster status: open or drafted

    Returns the best-matching candidate, or None if no match.
    """
    has_coords = grievance_lat is not None and grievance_lon is not None

    if has_coords:
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )
    else:
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.ward == extraction.ward)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )

    candidates = session.exec(statement).all()

    best_match: Optional[IssueCluster] = None
    best_score = -1.0

    # Compute grievance embedding once (cached by model)
    grievance_embedding = parse_embedding_json(
        embed_to_json(extraction.normalized_text)
    )
    effective_threshold = cosine_threshold if grievance_embedding is not None else similarity_threshold

    for cluster in candidates:
        if not _same_area(
            extraction.ward,
            grievance_lat, grievance_lon,
            cluster,
            haversine_threshold_m,
        ):
            continue

        score = _score_candidate(extraction, cluster, grievance_embedding)

        if score >= effective_threshold and score > best_score:
            best_score = score
            best_match = cluster

    return best_match


def update_cluster_embedding(
    cluster: IssueCluster,
    grievance_embedding_json: Optional[str],
) -> None:
    """Update the cluster centroid embedding when a grievance joins.

    Called by the route after a grievance is added to the cluster.
    No-op when embeddings are unavailable.
    """
    if not grievance_embedding_json:
        return
    new_vec = parse_embedding_json(grievance_embedding_json)
    if new_vec is None:
        return

    current_vec = parse_embedding_json(cluster.centroid_embedding_json)
    weight = cluster.coordinate_count  # grievances WITH coords only
    updated = update_centroid(current_vec, new_vec, weight)
    cluster.centroid_embedding_json = (
        embed_to_json("")  # we just compute JSON directly
    )

    # Actually, let's just serialise the list
    import json
    cluster.centroid_embedding_json = json.dumps(updated)
