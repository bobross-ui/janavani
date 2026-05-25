from typing import Optional

from sqlmodel import Session, select

from app.models import ComplaintDraft, Grievance, IssueCluster
from app.services.ai_provider import AIProvider, get_ai_provider


def generate_complaint_draft(
    session: Session,
    cluster_id: str,
    provider: Optional[AIProvider] = None,
) -> ComplaintDraft:
    """Generate a formal complaint draft for a cluster.

    Returns a persisted ComplaintDraft record.

    Parameters
    ----------
    session : Session
        Database session.
    cluster_id : str
        ID of the cluster to generate a draft for.
    provider : AIProvider, optional
        AI provider to use for draft generation. If None, the configured
        provider is obtained via get_ai_provider().
    """
    if provider is None:
        provider = get_ai_provider()

    cluster = session.get(IssueCluster, cluster_id)
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found")

    # Gather source grievances
    grievances = session.exec(
        select(Grievance).where(Grievance.cluster_id == cluster_id)
    ).all()

    source_ids = [g.id for g in grievances]

    # Build cluster_context for the AI provider
    area = f"Ward {cluster.ward}" if cluster.ward else cluster.landmark or "the affected area"
    sample_grievances = [
        {
            "id": g.id,
            "pii_redacted_text": g.pii_redacted_text or g.normalized_text or "Issue reported",
            "raw_text": g.raw_text or "",
            "consent_public": g.consent_public,
        }
        for g in grievances
        if g.consent_public
    ][:5]

    cluster_context = {
        "title": cluster.title or f"Public grievance — {cluster.issue_category}",
        "department": cluster.department,
        "area": area,
        "ward": cluster.ward or "",
        "language": "hi-IN",
        "grievance_count": cluster.grievance_count,
        "summary": cluster.summary or "Multiple citizens have reported this issue.",
        "sample_grievances": sample_grievances,
    }

    body = provider.generate_draft(cluster_context)

    draft = ComplaintDraft(
        cluster_id=cluster_id,
        title=cluster_context["title"],
        body=body,
        department=cluster.department,
        language="hi-IN",
        source_grievance_ids=",".join(source_ids),
        status="draft",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft
