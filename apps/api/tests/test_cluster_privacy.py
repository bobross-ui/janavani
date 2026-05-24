from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import (  # noqa: F401 — register models
    ClusterSupport,
    ComplaintDraft,
    EvalRun,
    Grievance,
    IssueCluster,
    User,
)


def _setup_test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    return engine


def test_cluster_detail_returns_only_redacted_public_samples():
    engine = _setup_test_db()
    with Session(engine) as session:
        user = User(phone_number="9999999999", display_name="Private User")
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water shortage",
            summary="No water",
        )
        session.add_all([user, cluster])
        session.commit()
        grievance = Grievance(
            user_id=user.id,
            raw_text="My number is 9999999999 and paani nahi aa raha",
            normalized_text="My number is 9999999999 and paani nahi aa raha",
            issue_category="water_supply",
            department="water_department",
            ward="8",
            cluster_id=cluster.id,
            pii_redacted_text="My number is [PHONE_REDACTED] and paani nahi aa raha",
            consent_public=True,
        )
        session.add(grievance)
        session.commit()
        cluster_id = cluster.id

    client = TestClient(app)
    response = client.get(f"/clusters/{cluster_id}")
    assert response.status_code == 200
    sample = response.json()["sample_grievances"][0]

    assert sample["pii_redacted_text"] == "My number is [PHONE_REDACTED] and paani nahi aa raha"
    assert "raw_text" not in sample
    assert "normalized_text" not in sample
    assert "user_id" not in sample
    assert "9999999999" not in str(sample)

    app.dependency_overrides.clear()
