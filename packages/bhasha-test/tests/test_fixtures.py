import json
from pathlib import Path

from bhasha_test.__main__ import _load_local_provider
from bhasha_test.evaluator import evaluate_cases


def test_janavani_seed_fixture_passes_local_provider():
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "janavani_seed.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))

    report = evaluate_cases(cases, _load_local_provider())

    assert report["summary"]["total_cases"] >= 6
    assert report["summary"]["overall_score"] == 1.0
    assert report["summary"]["redaction_safety"] == 1.0
