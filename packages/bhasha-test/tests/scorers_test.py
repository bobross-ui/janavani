import pytest
from bhasha_test.scorers import compute_wer, compute_draft_faithfulness, compute_p95_latency


# ── compute_wer tests ───────────────────────────────────────────────────────

class TestComputeWer:
    def test_both_empty_returns_zero(self):
        assert compute_wer("", "") == 0.0

    def test_exact_match_returns_zero(self):
        assert compute_wer("hello world", "hello world") == 0.0

    def test_single_substitution(self):
        wer = compute_wer("hello world", "hello there")
        # One substitution out of 2 words → 0.5
        assert wer == pytest.approx(0.5, abs=0.01)

    def test_hypothesis_extra_words(self):
        wer = compute_wer("hello world", "hello beautiful world")
        # Insertion of "beautiful" → 1 insertion / 2 ref words = 0.5
        assert wer == pytest.approx(0.5, abs=0.01)

    def test_reference_empty_hypothesis_nonempty(self):
        wer = compute_wer("", "hello world")
        # Both non-empty/empty scenarios return 1.0 (100% error)
        assert wer == 1.0

    def test_hypothesis_empty_reference_nonempty(self):
        wer = compute_wer("hello world", "")
        # 2 deletions → 2.0 (distance = 2, ref len = 2)
        assert wer == 1.0


# ── compute_draft_faithfulness tests ─────────────────────────────────────────

class TestComputeDraftFaithfulness:
    def test_empty_draft_returns_zero(self):
        assert compute_draft_faithfulness("", ["some source"]) == 0.0

    def test_none_draft_returns_zero(self):
        assert compute_draft_faithfulness(None, ["some source"]) == 0.0

    def test_no_contacts_in_draft_is_perfect(self):
        assert compute_draft_faithfulness("hello world", ["no contacts here"]) == 1.0

    def test_all_contacts_found_in_sources_returns_one(self):
        draft = "Call 9876543210 or email test@example.com"
        sources = [
            "Contact 9876543210 for help",
            "Send email to test@example.com please",
        ]
        assert compute_draft_faithfulness(draft, sources) == 1.0

    def test_hallucinated_phone_penalised(self):
        draft = "Call 9876543210"
        sources = ["No phone numbers in source"]
        score = compute_draft_faithfulness(draft, sources)
        assert score == 0.0

    def test_mixed_supported_and_hallucinated(self):
        draft = "Call 1111111111 or 2222222222 or email a@b.com"
        sources = ["Reach us at 1111111111", "Email a@b.com"]
        # draft has: 1111111111 (found), 2222222222 (not found), a@b.com (found)
        # 2 supported / 3 total
        score = compute_draft_faithfulness(draft, sources)
        assert score == pytest.approx(2 / 3, abs=0.01)

    def test_contacts_in_sources_but_not_draft_still_perfect(self):
        draft = "No contacts"
        sources = ["Call 9876543210"]
        assert compute_draft_faithfulness(draft, sources) == 1.0


# ── compute_p95_latency tests ───────────────────────────────────────────────

class TestComputeP95Latency:
    def test_empty_list_returns_zero(self):
        assert compute_p95_latency([]) == 0.0

    def test_single_element_returns_that_element(self):
        assert compute_p95_latency([42.0]) == 42.0

    def test_exact_95th_percentile_of_100_sorted(self):
        # 100 values: 0..99.  ceil(0.95*100)-1 = 94 → value 94.0
        latencies = list(range(100))
        assert compute_p95_latency(latencies) == 94.0

    def test_small_list(self):
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        # n=5, ceil(0.95*5)-1 = ceil(4.75)-1 = 5-1 = 4 → 50.0
        assert compute_p95_latency(latencies) == 50.0

    def test_unsorted_input_still_correct(self):
        latencies = [100.0, 5.0, 99.0, 1.0, 50.0, 75.0, 25.0, 60.0, 30.0, 10.0]
        # n=10, ceil(0.95*10)-1 = ceil(9.5)-1 = 10-1 = 9 → 100.0
        assert compute_p95_latency(latencies) == 100.0
