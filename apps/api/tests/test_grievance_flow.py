from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import (  # noqa: F401 — register models with SQLModel.metadata
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
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return engine


def _seed_user(session: Session) -> User:
    user = User(phone_number="9876543210", ward="8")
    session.add(user)
    session.commit()
    return user


class TestGrievanceFlow:
    def setup_method(self):
        self.engine = _setup_test_db()
        self.client = TestClient(app)

    def _session(self):
        return Session(self.engine)

    def test_submit_grievance_new_cluster(self):
        session = self._session()
        user = _seed_user(session)

        resp = self.client.post(
            "/grievances",
            json={
                "user_id": user.id,
                "text": "hamare ward 8 mein teen din se paani nahi aa raha",
                "language": "hi-Latn",
                "consent_public": True,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["extraction"]["category"] == "water_supply"
        assert data["extraction"]["ward"] == "8"
        assert data["extraction"]["urgency"] == "high"
        assert data["suggested_action"] == "create_cluster"
        assert data["matched_cluster_id"] is None
        assert data["grievance"]["id"]

    def test_second_similar_complaint_joins_cluster(self):
        session = self._session()
        user = _seed_user(session)

        # First grievance creates cluster
        resp1 = self.client.post(
            "/grievances",
            json={
                "user_id": user.id,
                "text": "ward 8 mein paani nahi aa raha teen din se",
                "language": "hi-Latn",
            },
        )
        assert resp1.status_code == 200
        assert resp1.json()["suggested_action"] == "create_cluster"

        # Create the cluster manually (since our MVP doesn't auto-create)
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water shortage Ward 8",
            summary="paani nahi aa raha ward 8 teen din",
            status="open",
        )
        session.add(cluster)
        session.commit()

        # Second grievance should join
        resp2 = self.client.post(
            "/grievances",
            json={
                "user_id": user.id,
                "text": "ward 8 mein nal sookha hai paani ki problem",
                "language": "hi-Latn",
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["suggested_action"] == "join_cluster"
        assert data2["matched_cluster_id"] == cluster.id

    def test_get_grievance_by_id(self):
        session = self._session()
        user = _seed_user(session)

        resp = self.client.post(
            "/grievances",
            json={
                "user_id": user.id,
                "text": "ward 8 paani",
                "language": "hi-Latn",
            },
        )
        gid = resp.json()["grievance"]["id"]

        get_resp = self.client.get(f"/grievances/{gid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == gid
        assert get_resp.json()["issue_category"] == "water_supply"

    def test_pii_not_in_response(self):
        session = self._session()
        user = _seed_user(session)

        resp = self.client.post(
            "/grievances",
            json={
                "user_id": user.id,
                "text": "Mera phone 9876543210 hai ward 5 mein paani nahi",
                "language": "hi-Latn",
            },
        )
        data = resp.json()
        assert "9876543210" not in data["extraction"]["pii_redacted_text"]
        assert "[PHONE_REDACTED]" in data["extraction"]["pii_redacted_text"]

    def test_get_nonexistent_grievance_returns_404(self):
        resp = self.client.get("/grievances/nonexistent-id")
        assert resp.status_code == 404
