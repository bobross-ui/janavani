"""Tests for draft_generation.py service — routing through AI provider."""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    ClusterSupport,
    ComplaintDraft,
    EvalRun,
    Grievance,
    IssueCluster,
    User,
)
from app.services.ai_provider import LocalAIProvider, SarvamAIProvider
from app.services.draft_generation import generate_complaint_draft
from app.services.sarvam_client import SarvamError


def _setup_test_engine():
    engine = create_engine(
        "sqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_cluster_with_grievances(session, consent_public=True):
    """Create a user, cluster, and grievance in the test DB."""
    user = User(phone_number="9876543210", ward="8")
    session.add(user)
    session.commit()

    cluster = IssueCluster(
        issue_category="water_supply",
        ward="8",
        title="Water shortage Ward 8",
        summary="No water for 4 days",
        department="water_department",
        grievance_count=5,
    )
    session.add(cluster)
    session.commit()

    g = Grievance(
        user_id=user.id,
        raw_text="paani nahi aa raha",
        normalized_text="paani nahi aa raha",
        issue_category="water_supply",
        ward="8",
        cluster_id=cluster.id,
        pii_redacted_text="paani nahi aa raha",
        consent_public=consent_public,
    )
    session.add(g)
    session.commit()

    return cluster, g


class TestDraftGenerationUsesProvider:
    """Tests that generate_complaint_draft routes through AI provider."""

    def setup_method(self):
        self.engine = _setup_test_engine()

    def _session(self):
        return Session(self.engine)

    def test_generate_draft_uses_local_provider_by_default(self):
        """With AI_PROVIDER=local, draft is generated via LocalAIProvider
        and contains template-style text."""
        with patch(
            "app.services.draft_generation.get_ai_provider",
            return_value=LocalAIProvider(),
        ):
            session = self._session()
            cluster, _ = _seed_cluster_with_grievances(session)

            draft = generate_complaint_draft(session, cluster.id)

            # Template-style text from LocalAIProvider
            assert "Water shortage Ward 8" in draft.title
            assert "We, the undersigned" in draft.body
            assert "Water_Department" in draft.body
            assert "5" in draft.body
            assert draft.language == "hi"
            assert draft.status == "draft"
            assert draft.cluster_id == cluster.id

    def test_generate_draft_routes_through_provider(self):
        """Inject a mock provider, verify it's called with correct
        cluster_context shape, verify returned text is used as draft body."""
        mock_provider = MagicMock()
        mock_provider.generate_draft.return_value = "Mock generated draft body text"

        session = self._session()
        cluster, grievance = _seed_cluster_with_grievances(session)

        draft = generate_complaint_draft(
            session, cluster.id, provider=mock_provider
        )

        # Verify provider.generate_draft was called
        mock_provider.generate_draft.assert_called_once()
        context_arg = mock_provider.generate_draft.call_args[0][0]

        # Check cluster_context shape
        assert isinstance(context_arg, dict)
        assert context_arg["title"] == cluster.title
        assert context_arg["department"] == cluster.department
        assert context_arg["grievance_count"] == cluster.grievance_count
        assert context_arg["summary"] == cluster.summary
        assert context_arg["language"] == "hi"
        assert "Ward 8" in context_arg["area"]
        assert isinstance(context_arg["sample_grievances"], list)
        assert len(context_arg["sample_grievances"]) == 1
        assert context_arg["sample_grievances"][0]["pii_redacted_text"] == "paani nahi aa raha"

        # Verify returned text was used as draft body
        assert draft.body == "Mock generated draft body text"
        assert draft.title == cluster.title

    def test_generate_draft_persists_complaint_draft_row(self):
        """Verify ComplaintDraft row is created in DB with correct fields."""
        mock_provider = MagicMock()
        mock_provider.generate_draft.return_value = "Persisted draft body"

        session = self._session()
        cluster, _ = _seed_cluster_with_grievances(session)

        draft = generate_complaint_draft(
            session, cluster.id, provider=mock_provider
        )

        # Verify returned draft has an ID (was persisted)
        assert draft.id is not None
        assert draft.cluster_id == cluster.id
        assert draft.body == "Persisted draft body"
        assert draft.department == cluster.department
        assert draft.status == "draft"
        assert draft.language == "hi"
        assert draft.source_grievance_ids != ""

        # Verify it's actually in the DB (re-query)
        from sqlmodel import select
        db_draft = session.exec(
            select(ComplaintDraft).where(ComplaintDraft.id == draft.id)
        ).first()
        assert db_draft is not None
        assert db_draft.body == "Persisted draft body"

    def test_generate_draft_handles_provider_error(self):
        """When provider raises SarvamError, the function should propagate it
        (FallbackAIProvider handles fallback at a higher level)."""
        mock_provider = MagicMock()
        mock_provider.generate_draft.side_effect = SarvamError("API failure")

        session = self._session()
        cluster, _ = _seed_cluster_with_grievances(session)

        with pytest.raises(SarvamError, match="API failure"):
            generate_complaint_draft(session, cluster.id, provider=mock_provider)

        # Verify no ComplaintDraft was persisted
        from sqlmodel import select
        drafts = session.exec(select(ComplaintDraft)).all()
        assert len(drafts) == 0

    def test_generate_draft_raises_for_missing_cluster(self):
        """Calling with a non-existent cluster_id raises ValueError."""
        session = self._session()
        with pytest.raises(ValueError, match="not found"):
            generate_complaint_draft(session, "nonexistent-id")

    def test_generate_draft_default_provider_is_used(self):
        """When no provider is passed (None), get_ai_provider() is called."""
        with patch(
            "app.services.draft_generation.get_ai_provider",
            return_value=LocalAIProvider(),
        ) as mock_factory:
            session = self._session()
            cluster, _ = _seed_cluster_with_grievances(session)

            generate_complaint_draft(session, cluster.id)

            mock_factory.assert_called_once()

    def test_generate_draft_context_aggregates_all_grievances(self):
        """Verify sample_grievances includes up to 5 grievances with consent_public."""
        session = self._session()
        user = User(phone_number="9876543210", ward="8")
        session.add(user)
        session.commit()

        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Multi-grievance cluster",
            summary="Multiple reports",
            department="water_department",
            grievance_count=7,
        )
        session.add(cluster)
        session.commit()

        # Add 8 grievances, only 6 with consent_public
        for i in range(6):
            g = Grievance(
                user_id=user.id,
                raw_text=f"grievance {i}",
                normalized_text=f"grievance {i}",
                issue_category="water_supply",
                ward="8",
                cluster_id=cluster.id,
                pii_redacted_text=f"redacted grievance {i}",
                consent_public=True,
            )
            session.add(g)
        for i in range(6, 8):
            g = Grievance(
                user_id=user.id,
                raw_text=f"private grievance {i}",
                normalized_text=f"private grievance {i}",
                issue_category="water_supply",
                ward="8",
                cluster_id=cluster.id,
                pii_redacted_text=f"private redacted {i}",
                consent_public=False,
            )
            session.add(g)
        session.commit()

        mock_provider = MagicMock()
        mock_provider.generate_draft.return_value = "test draft"

        generate_complaint_draft(session, cluster.id, provider=mock_provider)

        context_arg = mock_provider.generate_draft.call_args[0][0]
        samples = context_arg["sample_grievances"]
        # Only consent_public grievances, capped at 5
        assert len(samples) == 5
        for s in samples:
            assert s["consent_public"] is True

    def test_generate_draft_context_includes_ward(self):
        """Verify cluster_context includes ward field."""
        mock_provider = MagicMock()
        mock_provider.generate_draft.return_value = "draft"

        session = self._session()
        cluster, _ = _seed_cluster_with_grievances(session)

        generate_complaint_draft(session, cluster.id, provider=mock_provider)

        context_arg = mock_provider.generate_draft.call_args[0][0]
        assert context_arg["ward"] == "8"

    def test_generate_draft_context_includes_source_ids(self):
        """Verify source_grievance_ids field is set correctly."""
        mock_provider = MagicMock()
        mock_provider.generate_draft.return_value = "draft"

        session = self._session()
        cluster, grievance = _seed_cluster_with_grievances(session)

        draft = generate_complaint_draft(session, cluster.id, provider=mock_provider)

        assert grievance.id in draft.source_grievance_ids
