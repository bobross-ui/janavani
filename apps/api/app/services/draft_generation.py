from sqlmodel import Session, select

from app.models import ComplaintDraft, Grievance, IssueCluster


def generate_complaint_draft(
    session: Session, cluster_id: str
) -> ComplaintDraft:
    """Generate a formal complaint draft for a cluster.

    Returns a persisted ComplaintDraft record.
    """
    cluster = session.get(IssueCluster, cluster_id)
    if not cluster:
        raise ValueError(f"Cluster {cluster_id} not found")

    # Gather source grievances
    grievances = session.exec(
        select(Grievance).where(Grievance.cluster_id == cluster_id)
    ).all()

    source_ids = [g.id for g in grievances]

    body = _compose_draft_body(cluster, grievances)

    draft = ComplaintDraft(
        cluster_id=cluster_id,
        title=cluster.title or f"Public grievance — {cluster.issue_category}",
        body=body,
        department=cluster.department,
        language="hi",
        source_grievance_ids=",".join(source_ids),
        status="draft",
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft


def _compose_draft_body(
    cluster: IssueCluster, grievances: list[Grievance]
) -> str:
    dept = cluster.department.replace("_", " ").title()
    area = f"Ward {cluster.ward}" if cluster.ward else cluster.landmark or "the affected area"

    lines = [
        f"To,",
        f"The {dept},",
        "",
        f"Subject: {cluster.title or 'Public Grievance'}",
        "",
        "Respected Sir/Madam,",
        "",
        f"We, the undersigned {cluster.grievance_count} citizens of {area}, "
        f"wish to bring the following issue to your attention:",
        "",
        cluster.summary or "Multiple citizens have reported this issue.",
        "",
    ]

    # Add representative redacted quotes (up to 3)
    sample = [g for g in grievances if g.consent_public][:3]
    if sample:
        lines.append("Representative citizen reports:")
        for g in sample:
            text = g.pii_redacted_text or g.normalized_text or "Issue reported"
            lines.append(f"- {text}")
        lines.append("")

    lines.extend([
        f"This issue has been reported by {cluster.grievance_count} citizens "
        f"over the past several days. The matter requires urgent attention "
        f"as it affects daily life in {area}.",
        "",
        "We request that immediate action be taken to resolve this issue.",
        "",
        "Thank you,",
        f"Concerned Citizens of {area}",
    ])

    return "\n".join(lines)
