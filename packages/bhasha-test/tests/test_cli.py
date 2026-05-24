import json
import subprocess
import sys
from pathlib import Path


def test_cli_evaluates_fixture_and_writes_json_report(tmp_path):
    fixture = tmp_path / "cases.json"
    output = tmp_path / "report.json"
    fixture.write_text(json.dumps([
        {
            "id": "hi-water-phone",
            "text": "ward 8 me 9876543210 paani nahi aa raha",
            "language": "hi",
            "expected": {
                "category": "water_supply",
                "department": "water_department",
                "urgency": "high",
                "ward": "8"
            },
            "sensitive": ["9876543210"],
            "expected_redactions": ["[PHONE_REDACTED]"]
        }
    ]), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "bhasha_test", "evaluate", str(fixture), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "total_cases=1" in result.stdout
    assert output.exists()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"]["total_cases"] == 1
    assert report["summary"]["redaction_safety"] == 1.0
    assert "9876543210" not in output.read_text(encoding="utf-8")


def test_cli_rejects_empty_fixtures(tmp_path):
    fixture = tmp_path / "empty.json"
    fixture.write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "bhasha_test", "evaluate", str(fixture)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "at least one case" in result.stderr
