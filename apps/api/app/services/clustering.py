from typing import Optional

from sqlmodel import Session, select

from app.models import IssueCluster
from app.schemas import ExtractionResult
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
    """Check whether a grievance and cluster are in the same area.

    - Same ward number → match (strict).
    - If coords are present on both sides and within haversine_threshold_m,
      allow an override even when wards differ (e.g., opposite sides of
      the same intersection across a ward boundary).
    """
    # Strict ward match
    if extraction_ward and cluster.ward and extraction_ward == cluster.ward:
        return True

    # Haversine override: coords available on both sides
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


def find_matching_cluster(
    session: Session,
    extraction: ExtractionResult,
    similarity_threshold: float = 0.15,
    haversine_threshold_m: float = 300.0,
    grievance_lat: Optional[float] = None,
    grievance_lon: Optional[float] = None,
) -> Optional[IssueCluster]:
    """Find the best matching cluster for a grievance.

    Match conditions:
    - Same issue category
    - Same area (ward match or haversine ≤ threshold)
    - Token overlap above threshold
    - Cluster status is open or drafted

    Returns the candidate with the highest token overlap (best match).
    When coords are absent, the query pre-filters by ward for efficiency.
    """
    has_coords = grievance_lat is not None and grievance_lon is not None

    if has_coords:
        # Coords present: fetch all category matches and filter in Python
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )
    else:
        # No coords: pre-filter by ward for efficiency
        statement = (
            select(IssueCluster)
            .where(IssueCluster.issue_category == extraction.category)
            .where(IssueCluster.ward == extraction.ward)
            .where(IssueCluster.status.in_(["open", "drafted"]))
        )

    candidates = session.exec(statement).all()

    best_match: Optional[IssueCluster] = None
    best_overlap = similarity_threshold

    for cluster in candidates:
        if not _same_area(
            extraction.ward,
            grievance_lat, grievance_lon,
            cluster,
            haversine_threshold_m,
        ):
            continue

        if cluster.summary:
            overlap = _token_overlap(extraction.normalized_text, cluster.summary)
        else:
            overlap = _token_overlap(extraction.normalized_text, cluster.title)

        if overlap > best_overlap:
            best_overlap = overlap
            best_match = cluster

    return best_match
