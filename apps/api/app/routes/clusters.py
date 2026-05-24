from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import ClusterSupport, Grievance, IssueCluster
from app.schemas import (
    ClusterDetail,
    ClusterRead,
    ClusterSupportCreate,
    GrievanceRead,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


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


@router.get("", response_model=list[ClusterRead])
def list_clusters(
    ward: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: Session = Depends(get_session),
) -> list[ClusterRead]:
    statement = select(IssueCluster)
    if ward:
        statement = statement.where(IssueCluster.ward == ward)
    if category:
        statement = statement.where(IssueCluster.issue_category == category)
    if status:
        statement = statement.where(IssueCluster.status == status)
    statement = statement.order_by(IssueCluster.grievance_count.desc())
    clusters = session.exec(statement).all()
    return [_cluster_to_read(c) for c in clusters]


@router.get("/{cluster_id}", response_model=ClusterDetail)
def get_cluster(
    cluster_id: str, session: Session = Depends(get_session)
) -> ClusterDetail:
    cluster = session.get(IssueCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Fetch sample grievances (public consented only, redacted)
    grievances = session.exec(
        select(Grievance)
        .where(
            Grievance.cluster_id == cluster_id,
            Grievance.consent_public == True,  # noqa: E712
        )
        .limit(10)
    ).all()
    sample = [
        GrievanceRead(
            id=g.id,
            user_id=g.user_id,
            raw_text="[redacted]",
            transcript_text=g.transcript_text,
            normalized_text=g.normalized_text,
            language=g.language,
            issue_category=g.issue_category,
            department=g.department,
            urgency=g.urgency,
            ward=g.ward,
            landmark=g.landmark,
            latitude=g.latitude,
            longitude=g.longitude,
            pii_redacted_text=g.pii_redacted_text,
            cluster_id=g.cluster_id,
            status=g.status,
            consent_public=g.consent_public,
            created_at=g.created_at,
        )
        for g in grievances
    ]

    return ClusterDetail(
        id=cluster.id,
        title=cluster.title,
        summary=cluster.summary,
        issue_category=cluster.issue_category,
        department=cluster.department,
        ward=cluster.ward,
        landmark=cluster.landmark,
        status=cluster.status,
        support_count=cluster.support_count,
        grievance_count=cluster.grievance_count,
        urgency_score=cluster.urgency_score,
        centroid_latitude=cluster.centroid_latitude,
        centroid_longitude=cluster.centroid_longitude,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        sample_grievances=sample,
    )


@router.post("/{cluster_id}/support")
def support_cluster(
    cluster_id: str,
    body: ClusterSupportCreate,
    session: Session = Depends(get_session),
) -> dict:
    cluster = session.get(IssueCluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    grievance = session.get(Grievance, body.grievance_id)
    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")

    support = ClusterSupport(
        cluster_id=cluster_id,
        user_id=body.user_id,
        grievance_id=body.grievance_id,
        consent_to_file=body.consent_to_file,
    )
    session.add(support)
    cluster.support_count += 1
    if body.consent_to_file:
        # Already handled via the support record
        pass
    session.add(cluster)
    session.commit()

    return {"status": "supported", "support_count": cluster.support_count}
