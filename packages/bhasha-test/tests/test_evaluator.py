from bhasha_test.evaluator import evaluate_cases


class StubProvider:
    def extract_grievance(self, text, language="hi"):
        return {
            "category": "water_supply",
            "department": "water_department",
            "urgency": "high",
            "ward": "8",
            "language": language,
            "normalized_text": text.strip(),
            "pii_redacted_text": text.replace("9876543210", "[PHONE_REDACTED]"),
        }


def test_evaluate_cases_scores_field_accuracy_and_redaction():
    cases = [
        {
            "id": "hi-water-ward-8",
            "text": "ward 8 me 9876543210 paani nahi aa raha",
            "language": "hi",
            "expected": {
                "category": "water_supply",
                "department": "water_department",
                "urgency": "high",
                "ward": "8",
            },
            "sensitive": ["9876543210"],
            "expected_redactions": ["[PHONE_REDACTED]"],
        }
    ]

    report = evaluate_cases(cases, StubProvider())

    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["field_accuracy"]["category"] == 1.0
    assert report["summary"]["field_accuracy"]["department"] == 1.0
    assert report["summary"]["field_accuracy"]["urgency"] == 1.0
    assert report["summary"]["field_accuracy"]["ward"] == 1.0
    assert report["summary"]["redaction_safety"] == 1.0
    assert report["summary"]["overall_score"] == 1.0
    assert report["cases"][0]["passed"] is True


def test_evaluate_cases_records_failures_without_throwing():
    class BadProvider:
        def extract_grievance(self, text, language="hi"):
            return {
                "category": "sanitation",
                "department": "sanitation_department",
                "urgency": "medium",
                "ward": "",
                "language": language,
                "normalized_text": text,
                "pii_redacted_text": text,
            }

    cases = [
        {
            "id": "bad-case",
            "text": "ward 8 me phone 9876543210 paani nahi",
            "language": "hi",
            "expected": {"category": "water_supply", "ward": "8"},
            "sensitive": ["9876543210"],
            "expected_redactions": ["[PHONE_REDACTED]"],
        }
    ]

    report = evaluate_cases(cases, BadProvider())

    result = report["cases"][0]
    assert result["passed"] is False
    assert "category" in result["field_failures"]
    assert "ward" in result["field_failures"]
    assert "********10" in result["redaction_failures"]["leaked_sensitive"]
    assert "[PHONE_REDACTED]" in result["redaction_failures"]["missing_placeholders"]
    assert "9876543210" not in str(result)
    assert report["summary"]["redaction_safety"] == 0.0


def test_report_omits_raw_text_fields_that_can_contain_pii():
    cases = [
        {
            "id": "privacy-report",
            "text": "ward 8 me 9876543210 paani nahi",
            "language": "hi",
            "expected": {"category": "water_supply"},
            "sensitive": ["9876543210"],
            "expected_redactions": ["[PHONE_REDACTED]"],
        }
    ]

    report = evaluate_cases(cases, StubProvider())
    serialized = str(report)

    prediction = report["cases"][0]["prediction"]
    assert "normalized_text" not in prediction
    assert "raw_text" not in prediction
    assert "9876543210" not in serialized


def test_residual_pii_patterns_fail_redaction_even_if_sensitive_list_is_incomplete():
    cases = [
        {
            "id": "unlisted-phone",
            "text": "ward 8 me 9876543210 paani nahi",
            "language": "hi",
            "expected": {"category": "water_supply"},
            "sensitive": [],
            "expected_redactions": [],
        }
    ]

    class UnredactedProvider:
        def extract_grievance(self, text, language="hi"):
            return {
                "category": "water_supply",
                "department": "water_department",
                "urgency": "high",
                "ward": "8",
                "language": language,
                "normalized_text": text,
                "pii_redacted_text": text,
            }

    report = evaluate_cases(cases, UnredactedProvider())

    assert report["cases"][0]["passed"] is False
    assert "phone" in report["cases"][0]["redaction_failures"]["residual_pii"]


def test_empty_fixture_is_invalid():
    try:
        evaluate_cases([], StubProvider())
    except ValueError as exc:
        assert "at least one case" in str(exc)
    else:
        raise AssertionError("empty fixtures should be rejected")
