from app.models import ClusterSupport, ComplaintDraft, EvalRun, Grievance, IssueCluster, User


class TestUser:
    def test_create_user_gives_id(self):
        user = User(phone_number="9876543210")
        assert user.id
        assert user.id != ""

    def test_user_defaults(self):
        user = User(phone_number="9876543210")
        assert user.preferred_language == "hi"
        assert user.ward == ""
        assert user.display_name == ""


class TestGrievance:
    def test_create_grievance_stores_raw_text_and_category(self):
        g = Grievance(
            user_id="u1",
            raw_text="paani nahi aa raha",
            issue_category="water_supply",
        )
        assert g.raw_text == "paani nahi aa raha"
        assert g.issue_category == "water_supply"
        assert g.id
        assert g.status == "submitted"

    def test_grievance_defaults(self):
        g = Grievance(user_id="u1")
        assert g.urgency == "medium"
        assert g.language == "hi"
        assert g.consent_public is True
        assert g.cluster_id is None


class TestIssueCluster:
    def test_create_cluster_stores_category_and_ward(self):
        c = IssueCluster(issue_category="water_supply", ward="8")
        assert c.issue_category == "water_supply"
        assert c.ward == "8"
        assert c.id
        assert c.status == "open"

    def test_cluster_defaults(self):
        c = IssueCluster()
        assert c.support_count == 0
        assert c.grievance_count == 0
        assert c.urgency_score == 0.0


class TestClusterSupport:
    def test_create_support_record(self):
        s = ClusterSupport(
            cluster_id="c1",
            user_id="u1",
            grievance_id="g1",
            consent_to_file=True,
        )
        assert s.cluster_id == "c1"
        assert s.user_id == "u1"
        assert s.grievance_id == "g1"
        assert s.consent_to_file is True
        assert s.id


class TestComplaintDraft:
    def test_create_draft(self):
        d = ComplaintDraft(
            cluster_id="c1",
            title="Water shortage in Ward 8",
            body="Residents report no water for 3 days.",
            department="water_department",
        )
        assert d.cluster_id == "c1"
        assert d.title == "Water shortage in Ward 8"
        assert d.status == "draft"
        assert d.id


class TestEvalRun:
    def test_create_eval_run(self):
        e = EvalRun(name="smoke-test", total_cases=10, passed_cases=8)
        assert e.name == "smoke-test"
        assert e.total_cases == 10
        assert e.passed_cases == 8
        assert e.id
