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

    def test_cross_language_tamil_matches_english_cluster(self):
        """Tamil text grievance matches an English-summary cluster via translate_text to English pivot."""
        session = self._session()

        # Create a cluster about Ward 8 water with English summary
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Ward 8 water problem",
            summary="no water supply ward 8",
            status="open",
        )
        session.add(cluster)
        session.commit()

        # Mock provider: extract_grievance returns Tamil extraction;
        # translate_text must be called with the English pivot to produce
        # tokens that match the cluster summary.
        class MockProvider:
            def extract_grievance(self, text, language="hi"):
                return ExtractionResult(
                    category="water_supply",
                    ward="8",
                    language="ta",
                    # Tamil text before the pivot step — translate_text mock
                    # is what produces the English string clustering compares.
                    normalized_text="தண்ணீர் வரவில்லை வார்டு 8",
                )

            def translate_text(self, text, target_language, source_language=None):
                # Regression guard: the pivot MUST be English — a drive-by
                # config revert to "hi" must break this assertion.
                assert target_language == "en", (
                    f"clustering pivot must be English, got {target_language}"
                )
                return "no water supply ward 8"

            def transcribe_audio(self, audio_bytes, language_code="hi-IN", model=None):
                from app.schemas import TranscriptionResult
                return TranscriptionResult(transcript="", detected_language="hi-IN", confidence=0.0)

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

    def test_text_and_voice_tamil_same_issue_join_same_cluster(self):
        """Tamil text and Tamil voice complaints about the same issue must cluster together.

        This is the regression test for the dual-pivot bug: before the fix, a
        Tamil text complaint (translated to Hindi for clustering) and a Tamil
        voice complaint (STT-translate → English) produced tokens in different
        languages and never matched. After the fix, both paths converge on
        English so they land in the same cluster.
        """
        session = self._session()

        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Ward 8 water problem",
            summary="no water supply ward 8",
            status="open",
        )
        session.add(cluster)
        session.commit()

        # Mock that simulates BOTH paths correctly:
        # - Text path: extract returns Tamil, translate_text → English
        # - Voice path: extract returns English directly (STT-translate already
        #   produced English), translate_text is a pass-through
        class MockProvider:
            def extract_grievance(self, text, language="hi"):
                if language in ("en-IN", "en"):
                    # Voice path: STT-translate already produced English
                    return ExtractionResult(
                        category="water_supply",
                        ward="8",
                        language="en-IN",
                        normalized_text=text,
                    )
                # Text path: returns Tamil extraction
                return ExtractionResult(
                    category="water_supply",
                    ward="8",
                    language="ta",
                    normalized_text="தண்ணீர் வரவில்லை வார்டு 8",
                )

            def translate_text(self, text, target_language, source_language=None):
                assert target_language == "en", (
                    f"clustering pivot must be English, got {target_language}"
                )
                if source_language == "ta":
                    return "no water supply ward 8"
                # voice path: already English, pass through
                return text

            def transcribe_audio(self, audio_bytes, language_code="hi-IN", model=None):
                from app.schemas import TranscriptionResult
                return TranscriptionResult(
                    transcript="", detected_language="hi-IN", confidence=0.0
                )

            def generate_draft(self, cluster_context):
                return ""

        provider = MockProvider()

        # ── Text path: Tamil text grievance ──
        text_body = GrievanceCreate(
            user_id="user-1",
            text="தண்ணீர் வரவில்லை வார்டு 8",
            language="ta",
        )
        text_resp = submit_grievance(text_body, provider, session)
        assert text_resp.suggested_action == "join_cluster", text_resp
        text_cluster_id = text_resp.matched_cluster_id
        assert text_cluster_id == cluster.id

        # ── Voice path: STT-translate → English transcript → extraction ──
        voice_body = GrievanceCreate(
            user_id="user-2",
            text="no water in ward 8 for four days",
            language="en-IN",
        )
        voice_resp = submit_grievance(voice_body, provider, session)
        assert voice_resp.suggested_action == "join_cluster", voice_resp
        voice_cluster_id = voice_resp.matched_cluster_id

        # Both paths must converge on the same cluster
        assert text_cluster_id == voice_cluster_id, (
            f"dual-pivot bug: text → cluster {text_cluster_id}, "
            f"voice → cluster {voice_cluster_id}"
        )

    def test_haversine_override_crosses_ward_boundary(self):
        """Two grievances <300m apart but in different wards → same cluster."""
        session = self._session()

        # Create a water cluster with centroid in Ward 8 area
        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Water issue near ward boundary",
            summary="no water supply near boundary",
            status="open",
            centroid_latitude=19.0700,
            centroid_longitude=72.8800,
        )
        session.add(cluster)
        session.commit()

        # Grievance says Ward 9 but coords are ~200m from Ward 8 centroid
        result = _make_result(category="water_supply", ward="9", text="no water supply near boundary")
        match = find_matching_cluster(
            session, result,
            grievance_lat=19.0718,  # ~200m from cluster centroid
            grievance_lon=72.8800,
        )
        assert match is not None
        assert match.id == cluster.id

    def test_haversine_no_override_when_too_far(self):
        """Coords > 300m apart → no match despite same category + text."""
        session = self._session()

        cluster = IssueCluster(
            issue_category="water_supply",
            ward="8",
            title="Ward 8 water",
            summary="no water supply ward 8",
            status="open",
            centroid_latitude=19.0700,
            centroid_longitude=72.8800,
        )
        session.add(cluster)
        session.commit()

        # Grievance 2 km away — too far for haversine override
        result = _make_result(category="water_supply", ward="9", text="paani nahi aa raha")
        match = find_matching_cluster(
            session, result,
            grievance_lat=19.0900,  # ~2 km away
            grievance_lon=72.8950,
        )
        assert match is None
