from __future__ import annotations

import re
from typing import Any, Mapping, Protocol, Sequence

EVALUATED_FIELDS = ("category", "department", "urgency", "ward")
REQUIRED_CASE_KEYS = ("id", "text", "language", "expected", "sensitive", "expected_redactions")
SAFE_PREDICTION_FIELDS = ("category", "department", "urgency", "ward", "language", "pii_redacted_text")
RESIDUAL_PII_PATTERNS = {
    "phone": re.compile(r"\b\d{10}\b"),
    "aadhaar": re.compile(r"\b\d{12}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
}


class ExtractionProvider(Protocol):
    def extract_grievance(self, text: str, language: str = "hi") -> Any:
        ...


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {
        key: getattr(value, key)
        for key in EVALUATED_FIELDS + ("language", "normalized_text", "pii_redacted_text")
        if hasattr(value, key)
    }


def _mask_residual_pii(text: str) -> str:
    masked = text
    masked = RESIDUAL_PII_PATTERNS["email"].sub("[EMAIL_LEAK_MASKED]", masked)
    masked = RESIDUAL_PII_PATTERNS["aadhaar"].sub("[ID_LEAK_MASKED]", masked)
    masked = RESIDUAL_PII_PATTERNS["phone"].sub("[PHONE_LEAK_MASKED]", masked)
    return masked


def _safe_prediction(prediction: Mapping[str, Any]) -> dict[str, Any]:
    safe = {field: prediction.get(field, "") for field in SAFE_PREDICTION_FIELDS}
    safe["pii_redacted_text"] = _mask_residual_pii(str(safe.get("pii_redacted_text", "")))
    return safe


def _mask_sensitive(value: str) -> str:
    if len(value) <= 2:
        return "*" * len(value)
    return "*" * (len(value) - 2) + value[-2:]


def _validate_cases(cases: Sequence[Mapping[str, Any]]) -> None:
    if not cases:
        raise ValueError("fixture must contain at least one case")
    for index, case in enumerate(cases):
        for key in REQUIRED_CASE_KEYS:
            if key not in case:
                raise ValueError(f"case {index} missing required key: {key}")
        if not isinstance(case["expected"], Mapping):
            raise ValueError(f"case {index} expected must be an object")
        if not isinstance(case["sensitive"], list):
            raise ValueError(f"case {index} sensitive must be a list")
        if not isinstance(case["expected_redactions"], list):
            raise ValueError(f"case {index} expected_redactions must be a list")


def _score_field(expected: Mapping[str, Any], prediction: Mapping[str, Any], field: str) -> tuple[bool, dict[str, Any] | None]:
    if field not in expected:
        return True, None
    expected_value = str(expected.get(field, ""))
    predicted_value = str(prediction.get(field, ""))
    if predicted_value == expected_value:
        return True, None
    return False, {"expected": expected_value, "predicted": predicted_value}


def _redaction_failures(case: Mapping[str, Any], prediction: Mapping[str, Any]) -> dict[str, list[str]]:
    redacted = str(prediction.get("pii_redacted_text", ""))
    leaked_sensitive = [
        _mask_sensitive(str(value))
        for value in case.get("sensitive", [])
        if value and str(value) in redacted
    ]
    missing_placeholders = [
        str(value) for value in case.get("expected_redactions", []) if value and str(value) not in redacted
    ]
    residual_pii = [label for label, pattern in RESIDUAL_PII_PATTERNS.items() if pattern.search(redacted)]
    return {
        "leaked_sensitive": leaked_sensitive,
        "missing_placeholders": missing_placeholders,
        "residual_pii": residual_pii,
    }


def evaluate_cases(cases: Sequence[Mapping[str, Any]], provider: ExtractionProvider) -> dict[str, Any]:
    _validate_cases(cases)
    results: list[dict[str, Any]] = []
    field_totals = {field: 0 for field in EVALUATED_FIELDS}
    field_correct = {field: 0 for field in EVALUATED_FIELDS}
    redaction_passes = 0

    for case in cases:
        prediction = _to_dict(
            provider.extract_grievance(str(case["text"]), str(case.get("language", "hi")))
        )
        expected = case.get("expected", {})
        field_failures: dict[str, dict[str, Any]] = {}

        for field in EVALUATED_FIELDS:
            if field not in expected:
                continue
            field_totals[field] += 1
            passed, failure = _score_field(expected, prediction, field)
            if passed:
                field_correct[field] += 1
            elif failure is not None:
                field_failures[field] = failure

        redaction_failures = _redaction_failures(case, prediction)
        redaction_passed = not any(redaction_failures.values())
        if redaction_passed:
            redaction_passes += 1

        passed = not field_failures and redaction_passed
        results.append(
            {
                "id": case.get("id", ""),
                "passed": passed,
                "expected": dict(expected),
                "prediction": _safe_prediction(prediction),
                "field_failures": field_failures,
                "redaction_failures": redaction_failures,
            }
        )

    field_accuracy = {
        field: (field_correct[field] / field_totals[field] if field_totals[field] else 1.0)
        for field in EVALUATED_FIELDS
    }
    scored_fields = [field for field in EVALUATED_FIELDS if field_totals[field] > 0]
    extraction_score = (
        sum(field_accuracy[field] for field in scored_fields) / len(scored_fields)
        if scored_fields else 0.0
    )
    redaction_safety = redaction_passes / len(cases)
    overall_score = (extraction_score + redaction_safety) / 2

    report: dict[str, Any] = {
        "summary": {
            "total_cases": len(cases),
            "passed_cases": sum(1 for result in results if result["passed"]),
            "field_accuracy": field_accuracy,
            "extraction_score": extraction_score,
            "redaction_safety": redaction_safety,
            "overall_score": overall_score,
        },
        "cases": results,
    }
    return report


def attach_scorer_results(
    report: dict[str, Any],
    *,
    wer_scores: list[float] | None = None,
    draft_scores: list[float] | None = None,
    latency_ms: list[float] | None = None,
) -> dict[str, Any]:
    """Attach WER, draft-faithfulness, and latency scores to an eval report.

    Callers that have access to audio transcription or draft generation
    can populate these extra metrics after the core extraction eval.
    """
    from .scorers import mean, p95

    extra: dict[str, Any] = {}
    if wer_scores:
        extra["wer_mean"] = mean(wer_scores)
        extra["wer_p95"] = p95(wer_scores)

    if draft_scores:
        extra["draft_faithfulness_mean"] = mean(draft_scores)

    if latency_ms:
        extra["latency_mean_ms"] = mean(latency_ms)
        extra["latency_p95_ms"] = p95(latency_ms)

    if extra:
        report["summary"]["scorer_metrics"] = extra

    return report
