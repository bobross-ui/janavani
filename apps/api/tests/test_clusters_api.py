from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import (  # noqa: F401
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


class TestClustersAPI:
    def setup_method(self):
        self.engine = _setup_test_db()
        self.client = TestClient(app)

    def _session(self):
        return Session(self.engine)

    def test_list_clusters_empty(self):
        resp = self.client.get("/clusters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_clusters_with_data(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water shortage",
            grievance_count=5,
        )
        session.add(cluster)
        session.commit()

        resp = self.client.get("/clusters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ward"] == "8"

    def test_list_clusters_filter_by_ward(self):
        session = self._session()
        c1 = IssueCluster(issue_category="water", ward="8", title="w")
        c2 = IssueCluster(issue_category="water", ward="9", title="w")
        session.add_all([c1, c2])
        session.commit()

        resp = self.client.get("/clusters?ward=8")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["ward"] == "8"

    def test_support_cluster_increments_count(self):
        session = self._session()
        user = _seed_user(session)
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water",
        )
        grievance = Grievance(
            user_id=user.id,
            raw_text="paani nahi",
            issue_category="water_supply",
            ward="8",
            cluster_id=cluster.id,
        )
        session.add_all([cluster, grievance])
        session.commit()

        resp = self.client.post(
            f"/clusters/{cluster.id}/support",
            json={
                "user_id": user.id,
                "grievance_id": grievance.id,
                "consent_to_file": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["support_count"] == 1

    def test_support_cluster_idempotent(self):
        """Duplicate support should return already_supported."""
        session = self._session()
        user = _seed_user(session)
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water",
        )
        grievance = Grievance(
            user_id=user.id,
            raw_text="paani nahi",
            issue_category="water_supply",
            ward="8",
            cluster_id=cluster.id,
        )
        session.add_all([cluster, grievance])
        session.commit()

        body = {
            "user_id": user.id,
            "grievance_id": grievance.id,
            "consent_to_file": True,
        }
        r1 = self.client.post(f"/clusters/{cluster.id}/support", json=body)
        assert r1.status_code == 200
        assert r1.json()["status"] == "supported"
        assert r1.json()["support_count"] == 1

        r2 = self.client.post(f"/clusters/{cluster.id}/support", json=body)
        assert r2.status_code == 200
        assert r2.json()["status"] == "already_supported"
        assert r2.json()["support_count"] == 1  # not incremented

    def test_support_cluster_rejects_other_users_grievance(self):
        """403 when grievance.user_id != body.user_id."""
        session = self._session()
        user_a = _seed_user(session)
        user_b = User(phone_number="1111111111", ward="8")
        session.add(user_b)
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water",
        )
        grievance = Grievance(
            user_id=user_b.id,
            raw_text="paani nahi",
            issue_category="water_supply",
            ward="8",
            cluster_id=cluster.id,
        )
        session.add_all([cluster, grievance])
        session.commit()

        resp = self.client.post(
            f"/clusters/{cluster.id}/support",
            json={
                "user_id": user_a.id,  # different from grievance.user_id
                "grievance_id": grievance.id,
                "consent_to_file": True,
            },
        )
        assert resp.status_code == 403

    def test_support_cluster_rejects_wrong_cluster_grievance(self):
        """400 when grievance.cluster_id != cluster_id."""
        session = self._session()
        user = _seed_user(session)
        cluster_a = IssueCluster(
            issue_category="water_supply", ward="8", title="Water A",
        )
        cluster_b = IssueCluster(
            issue_category="sanitation", ward="8", title="Water B",
        )
        grievance = Grievance(
            user_id=user.id,
            raw_text="paani nahi",
            issue_category="water_supply",
            ward="8",
            cluster_id=cluster_a.id,
        )
        session.add_all([cluster_a, cluster_b, grievance])
        session.commit()

        resp = self.client.post(
            f"/clusters/{cluster_b.id}/support",
            json={
                "user_id": user.id,
                "grievance_id": grievance.id,
                "consent_to_file": True,
            },
        )
        assert resp.status_code == 400

    def test_support_cluster_rejects_missing_user(self):
        """404 when user doesn't exist."""
        session = self._session()
        cluster = IssueCluster(
            issue_category="water_supply", ward="8", title="Water",
        )
        session.add(cluster)
        session.commit()

        resp = self.client.post(
            f"/clusters/{cluster.id}/support",
            json={
                "user_id": "nonexistent-user",
                "grievance_id": "nonexistent-grievance",
                "consent_to_file": True,
            },
        )
        assert resp.status_code == 404

    def test_get_cluster_viewer_has_supported(self):
        """Cluster detail shows viewer_has_supported=true after support."""
        session = self._session()
        user = _seed_user(session)
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water",
        )
        grievance = Grievance(
            user_id=user.id,
            raw_text="paani nahi",
            issue_category="water_supply",
            ward="8",
            cluster_id=cluster.id,
        )
        session.add_all([cluster, grievance])
        session.commit()

        # Before support: false
        r0 = self.client.get(f"/clusters/{cluster.id}?user_id={user.id}")
        assert r0.status_code == 200
        assert r0.json()["viewer_has_supported"] == False

        # After support: true
        self.client.post(
            f"/clusters/{cluster.id}/support",
            json={
                "user_id": user.id,
                "grievance_id": grievance.id,
                "consent_to_file": True,
            },
        )
        r1 = self.client.get(f"/clusters/{cluster.id}?user_id={user.id}")
        assert r1.status_code == 200
        assert r1.json()["viewer_has_supported"] == True


class TestAdminAPI:
    def setup_method(self):
        self.engine = _setup_test_db()
        self.client = TestClient(app)

    def _session(self):
        return Session(self.engine)

    def test_generate_draft(self):
        session = self._session()
        user = _seed_user(session)
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water shortage Ward 8",
            summary="No water for 4 days",
            department="water_department",
            grievance_count=5,
        )
        g = Grievance(
            user_id=user.id,
            raw_text="paani nahi aa raha",
            issue_category="water_supply",
            ward="8",
            cluster_id=cluster.id,
            pii_redacted_text="paani nahi aa raha",
            consent_public=True,
        )
        session.add_all([cluster, g])
        session.commit()

        resp = self.client.post(f"/admin/clusters/{cluster.id}/draft")
        assert resp.status_code == 200
        data = resp.json()
        assert "Water shortage" in data["title"]
        assert "4 days" in data["body"]
        assert data["department"] == "water_department"
        assert data["status"] == "draft"

    def test_draft_idempotent(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water", ward="8", title="Water",
        )
        session.add(cluster)
        session.commit()

        r1 = self.client.post(f"/admin/clusters/{cluster.id}/draft")
        r2 = self.client.post(f"/admin/clusters/{cluster.id}/draft")
        assert r1.json()["id"] == r2.json()["id"]

    def test_update_cluster_status(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water", ward="8", title="Water",
        )
        session.add(cluster)
        session.commit()

        resp = self.client.patch(
            f"/admin/clusters/{cluster.id}/status?status=resolved"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"
