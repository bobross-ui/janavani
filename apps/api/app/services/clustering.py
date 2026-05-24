from typing import Optional

from sqlmodel import Session, select

from app.models import IssueCluster
from app.schemas import ExtractionResult


def _token_overlap(text_a: str, text_b: str) -> float:
    """Jaccard token overlap between two strings."""
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def find_matching_cluster(
    session: Session,
    extraction: ExtractionResult,
    similarity_threshold: float = 0.15,
) -> Optional[IssueCluster]:
    """Find an existing cluster matching the extracted grievance.

    Match conditions:
    - Same issue category
    - Same ward
    - Token overlap above threshold
    - Cluster status is open or drafted
    """
    statement = (
        select(IssueCluster)
        .where(IssueCluster.issue_category == extraction.category)
        .where(IssueCluster.ward == extraction.ward)
        .where(IssueCluster.status.in_(["open", "drafted"]))
    )
    candidates = session.exec(statement).all()

    for cluster in candidates:
        if cluster.summary:
            overlap = _token_overlap(extraction.normalized_text, cluster.summary)
        else:
            overlap = _token_overlap(extraction.normalized_text, cluster.title)
        if overlap >= similarity_threshold:
            return cluster

    return None
