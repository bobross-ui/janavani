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


def test_created_cluster_summary_is_redacted(monkeypatch):
    """H2: an auto-created cluster's public summary must be PII-redacted.

    Before the fix the summary was set to raw normalized_text, leaking any
    phone/email/Aadhaar in the grievance onto the public dashboard.
    """
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    engine = _setup_test_db()
    with Session(engine) as session:
        user = User(phone_number="9876543210", display_name="A")
        session.add(user)
        session.commit()
        user_id = user.id

    client = TestClient(app)
    resp = client.post(
        "/grievances",
        json={
            "user_id": user_id,
            "text": "paani nahi aa raha, mera number 9876543210",
            "language": "hi",
            "consent_public": True,
        },
    )
    assert resp.status_code == 200
    cluster_id = resp.json()["grievance"]["cluster_id"]
    assert cluster_id

    summary = client.get(f"/clusters/{cluster_id}").json()["summary"]
    assert "9876543210" not in summary
    assert "[PHONE_REDACTED]" in summary

    app.dependency_overrides.clear()


def test_created_cluster_summary_withheld_without_consent(monkeypatch):
    """H4: a grievance with consent_public=False must not have its text
    published as the public cluster summary; it falls back to the generic
    location/category title."""
    monkeypatch.setenv("AI_PROVIDER", "local")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    engine = _setup_test_db()
    with Session(engine) as session:
        user = User(phone_number="9876543210", display_name="A")
        session.add(user)
        session.commit()
        user_id = user.id

    client = TestClient(app)
    resp = client.post(
        "/grievances",
        json={
            "user_id": user_id,
            "text": "kachra nahi uth raha, mera number 9876543210",
            "language": "hi",
            "consent_public": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    cluster_id = body["grievance"]["cluster_id"]
    assert cluster_id

    detail = client.get(f"/clusters/{cluster_id}").json()
    assert "9876543210" not in detail["summary"]
    # withheld → summary is the generic title, not the citizen's words
    assert detail["summary"] == detail["title"]

    app.dependency_overrides.clear()
