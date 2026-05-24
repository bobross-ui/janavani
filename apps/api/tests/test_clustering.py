from sqlmodel import Session, SQLModel, create_engine

from app.models import IssueCluster
from app.schemas import ExtractionResult
from app.services.clustering import find_matching_cluster


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
