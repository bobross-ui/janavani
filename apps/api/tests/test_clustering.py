from sqlmodel import Session, SQLModel, create_engine

from app.models import IssueCluster, Grievance
from app.schemas import ExtractionResult, GrievanceCreate
from app.services.clustering import find_matching_cluster
from app.routes.grievances import submit_grievance


def _make_result(category="water_supply", ward="8", text="paani nahi aa raha"):
    return ExtractionResult(
        category=category,
        ward=ward,
        normalized_text=text,
        language="hi",
    )


class TestFindMatchingCluster:
    def setup_method(self):
        self.engine = create_engine("sqlite://", echo=False)
        SQLModel.metadata.create_all(self.engine)

    def _session(self):
        return Session(self.engine)

    def test_matches_same_category_same_ward_similar_text(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="No water supply in Ward 8",
            summary="paani supply band hai ward 8",
            status="open",
        )
        session.add(cluster)
        session.commit()

        result = _make_result(text="paani nahi aa raha ward 8 mein")
        match = find_matching_cluster(session, result)
        assert match is not None
        assert match.id == cluster.id

    def test_no_match_different_category(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="sanitation",
            ward="8",
            title="Garbage in Ward 8",
            status="open",
        )
        session.add(cluster)
        session.commit()

        result = _make_result(category="water_supply", ward="8")
        match = find_matching_cluster(session, result)
        assert match is None

    def test_no_match_different_ward(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="9",
            title="Water issue Ward 9",
            status="open",
        )
        session.add(cluster)
        session.commit()

        result = _make_result(category="water_supply", ward="8")
        match = find_matching_cluster(session, result)
        assert match is None

    def test_no_match_when_no_clusters_exist(self):
        session = self._session()
        result = _make_result()
        match = find_matching_cluster(session, result)
        assert match is None

    def test_skips_resolved_clusters(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Old water issue",
            summary="paani band tha",
            status="resolved",
        )
        session.add(cluster)
        session.commit()

        result = _make_result(text="paani nahi aa raha ward 8 mein")
        match = find_matching_cluster(session, result)
        assert match is None

    def test_hindi_hinglish_both_match(self):
        session = self._session()
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water problem",
            summary="पानी नहीं आ रहा ward 8",
            status="open",
        )
        session.add(cluster)
        session.commit()

        # Hinglish input should still match via token overlap
        result = _make_result(text="ward 8 mein paani nahi aa raha")
        match = find_matching_cluster(session, result)
        assert match is not None

    def test_cross_language_tamil_matches_hindi_cluster(self):
        """Tamil grievance matches Hindi cluster after translation to pivot language."""
        session = self._session()

        # Create a Hindi cluster about Ward 8 water
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Ward 8 water problem",
            summary="paani nahi aa raha ward 8",
            status="open",
        )
        session.add(cluster)
        session.commit()

        # Mock provider: extract_grievance returns Tamil extraction;
        # translate_text returns Hindi with tokens matching the cluster summary
        class MockProvider:
            def extract_grievance(self, text, language="hi"):
                return ExtractionResult(
                    category="water_supply",
                    ward="8",
                    language="ta",
                    normalized_text="தண்ணீர் வரவில்லை வார்டு 8",
                )

            def translate_text(self, text, target_language, source_language=None):
                return "paani nahi aa raha ward 8"

            def transcribe_audio(self, audio_bytes):
                return ""

            def generate_draft(self, cluster_context):
                return ""

        provider = MockProvider()

        body = GrievanceCreate(
            user_id="user-1",
            text="தண்ணீர் வரவில்லை வார்டு 8",
            language="ta",
        )

        response = submit_grievance(body, provider, session)

        assert response.matched_cluster_id == cluster.id, (
            f"Expected cluster {cluster.id}, got {response.matched_cluster_id}"
        )
        assert response.suggested_action == "join_cluster"
