from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import ComplaintDraft, IssueCluster
from app.schemas import ClusterRead, ComplaintDraftRead
from app.services.draft_generation import generate_complaint_draft

router = APIRouter(prefix="/admin", tags=["admin"])


def _cluster_to_read(c: IssueCluster) -> ClusterRead:
    return ClusterRead(
        id=c.id,
        title=c.title,
        summary=c.summary,
        issue_category=c.issue_category,
        department=c.department,
        ward=c.ward,
        landmark=c.landmark,
        status=c.status,
        support_count=c.support_count,
        grievance_count=c.grievance_count,
        urgency_score=c.urgency_score,
        centroid_latitude=c.centroid_latitude,
        centroid_longitude=c.centroid_longitude,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/clusters", response_model=list[ClusterRead])
def list_admin_clusters(
    session: Session = Depends(get_session),
) -> list[ClusterRead]:
    statement = select(IssueCluster).order_by(
        IssueCluster.grievance_count.desc()
    )
    clusters = session.exec(statement).all()
    return [_cluster_to_read(c) for c in clusters]


@router.post("/clusters/{cluster_id}/draft", response_model=ComplaintDraftRead)
def create_draft(
    cluster_id: str, session: Session = Depends(get_session)
) -> ComplaintDraftRead:
    cluster = session.get(IssueCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Check for existing draft
    existing = session.exec(
        select(ComplaintDraft).where(ComplaintDraft.cluster_id == cluster_id)
    ).first()
    if existing:
        return _draft_to_read(existing)

    draft = generate_complaint_draft(session, cluster_id)
    return _draft_to_read(draft)


@router.patch("/clusters/{cluster_id}/status")
def update_cluster_status(
    cluster_id: str,
    status: str,
    session: Session = Depends(get_session),
) -> dict:
    cluster = session.get(IssueCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    valid = {"open", "drafted", "filed", "resolved"}
    if status not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid}",
        )

    cluster.status = status
    session.add(cluster)
    session.commit()
    return {"id": cluster_id, "status": status}


def _draft_to_read(d: ComplaintDraft) -> ComplaintDraftRead:
    return ComplaintDraftRead(
        id=d.id,
        cluster_id=d.cluster_id,
        title=d.title,
        body=d.body,
        department=d.department,
        language=d.language,
        source_grievance_ids=d.source_grievance_ids,
        status=d.status,
        created_at=d.created_at,
    )
