from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from .evaluator import evaluate_cases


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_local_provider() -> Any:
    api_path = _repo_root() / "apps" / "api"
    if str(api_path) not in sys.path:
        sys.path.insert(0, str(api_path))
    module = importlib.import_module("app.services.ai_provider")
    return module.LocalAIProvider()


def _read_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("fixture must be a JSON array of cases")
    return data


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evaluate_command(args: argparse.Namespace) -> int:
    try:
        cases = _read_cases(Path(args.fixture))
        provider = _load_local_provider()
        report = evaluate_cases(cases, provider)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.output:
        _write_report(Path(args.output), report)

    summary = report["summary"]
    print(
        " ".join(
            [
                f"total_cases={summary['total_cases']}",
                f"passed_cases={summary['passed_cases']}",
                f"overall_score={summary['overall_score']:.3f}",
                f"redaction_safety={summary['redaction_safety']:.3f}",
            ]
        )
    )
    return 0 if summary["passed_cases"] == summary["total_cases"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bhasha-test")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate extraction/redaction fixtures")
    evaluate.add_argument("fixture", help="Path to JSON fixture file")
    evaluate.add_argument("--output", help="Optional path to write JSON report")
    evaluate.set_defaults(func=evaluate_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
