from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import get_session
from app.models import ClusterSupport, Grievance, IssueCluster, User
from app.schemas import (
    ClusterDetail,
    ClusterRead,
    ClusterSupportCreate,
    RedactedGrievanceSample,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


def cluster_to_read(c: IssueCluster) -> ClusterRead:
    return ClusterRead(
        id=c.id,
        title=c.title,
        summary=c.summary,
        issue_category=c.issue_category,
        department=c.department,
        ward=c.ward,
        area=c.area,
        area_source=c.area_source,
        suburb=c.suburb,
        road=c.road,
        sector=c.sector,
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
    return [cluster_to_read(c) for c in clusters]


@router.get("/{cluster_id}", response_model=ClusterDetail)
def get_cluster(
    cluster_id: str,
    user_id: Optional[str] = Query(None, description="Current user ID to check support status"),
    session: Session = Depends(get_session),
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
        RedactedGrievanceSample(
            id=g.id,
            language=g.language,
            issue_category=g.issue_category,
            department=g.department,
            urgency=g.urgency,
            ward=g.ward,
            landmark=g.landmark,
            pii_redacted_text=g.pii_redacted_text or "[redacted sample unavailable]",
            status=g.status,
            created_at=g.created_at,
        )
        for g in grievances
    ]

    # Check if viewer already supported this cluster
    viewer_has_supported = False
    if user_id:
        support = session.exec(
            select(ClusterSupport).where(
                ClusterSupport.cluster_id == cluster_id,
                ClusterSupport.user_id == user_id,
            )
        ).first()
        viewer_has_supported = support is not None

    return ClusterDetail(
        id=cluster.id,
        title=cluster.title,
        summary=cluster.summary,
        issue_category=cluster.issue_category,
        department=cluster.department,
        ward=cluster.ward,
        area=cluster.area,
        area_source=cluster.area_source,
        suburb=cluster.suburb,
        road=cluster.road,
        sector=cluster.sector,
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
        viewer_has_supported=viewer_has_supported,
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

    # Enforce provenance: grievance must belong to the requesting user
    if grievance.user_id != body.user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot support a cluster with another user's grievance",
        )

    # Grievance must belong to this cluster
    if grievance.cluster_id != cluster_id:
        raise HTTPException(
            status_code=400,
            detail="Grievance does not belong to this cluster",
        )

    user = session.get(User, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Idempotency: one support per user per cluster
    existing = session.exec(
        select(ClusterSupport).where(
            ClusterSupport.cluster_id == cluster_id,
            ClusterSupport.user_id == body.user_id,
        )
    ).first()
    if existing:
        return {"status": "already_supported", "support_count": cluster.support_count}

    support = ClusterSupport(
        cluster_id=cluster_id,
        user_id=body.user_id,
        grievance_id=body.grievance_id,
        consent_to_file=body.consent_to_file,
    )
    session.add(support)
    cluster.support_count += 1
    if body.consent_to_file:
        pass
    session.add(cluster)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Race: another request inserted between our SELECT and INSERT.
        # Re-fetch the cluster for the current count.
        session.refresh(cluster)
        return {"status": "already_supported", "support_count": cluster.support_count}

    return {"status": "supported", "support_count": cluster.support_count}
