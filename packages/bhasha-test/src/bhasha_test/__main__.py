from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from .evaluator import evaluate_cases
from .http_eval import HttpEvalProvider


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _ensure_api_path() -> None:
    api_path = _repo_root() / "apps" / "api"
    if str(api_path) not in sys.path:
        sys.path.insert(0, str(api_path))


def _load_local_provider() -> Any:
    _ensure_api_path()
    module = importlib.import_module("app.services.ai_provider")
    return module.LocalAIProvider()


def _load_sarvam_provider() -> Any:
    _ensure_api_path()
    module = importlib.import_module("app.services.ai_provider")
    return module.SarvamAIProvider()


def _load_provider(name: str) -> Any:
    if name == "local":
        return _load_local_provider()
    if name == "sarvam":
        return _load_sarvam_provider()
    raise ValueError(f"unknown provider: {name}")


def _read_cases(path: Path) -> list[dict[str, Any]]:
    """Read fixture cases from JSON or YAML."""
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            raise ValueError(
                "YAML fixtures require PyYAML. Install with: pip install pyyaml"
            ) from None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("fixture must be an array of cases")
    return data


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _print_summary(report: dict[str, Any]) -> None:
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


def _print_per_field(report: dict[str, Any]) -> None:
    """Print per-field accuracy breakdown."""
    field_accuracy = report["summary"].get("field_accuracy", {})
    for field, acc in field_accuracy.items():
        print(f"  {field}_accuracy={acc:.3f}")


def evaluate_command(args: argparse.Namespace) -> int:
    fixture_path = Path(args.fixture)

    # HTTP target mode: POST cases to a live API
    if args.target:
        try:
            cases = _read_cases(fixture_path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        provider = HttpEvalProvider(args.target, args.provider)
        report = evaluate_cases(cases, provider)
        if args.output:
            _write_report(Path(args.output), report)
        _print_summary(report)
        _print_per_field(report)
        return 0 if report["summary"]["passed_cases"] == report["summary"]["total_cases"] else 1

    # In-process mode: load provider locally
    try:
        cases = _read_cases(fixture_path)
        provider = _load_provider(args.provider)
        report = evaluate_cases(cases, provider)
    except (ValueError, NotImplementedError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.output:
        _write_report(Path(args.output), report)

    _print_summary(report)
    _print_per_field(report)
    return 0 if report["summary"]["passed_cases"] == report["summary"]["total_cases"] else 1


def compare_command(args: argparse.Namespace) -> int:
    try:
        cases = _read_cases(Path(args.fixture))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    reports: dict[str, dict[str, Any]] = {}
    for name in ("local", "sarvam"):
        try:
            prov = _load_provider(name)
            report = evaluate_cases(cases, prov)
            reports[name] = report
        except NotImplementedError:
            reports[name] = {
                "summary": {
                    "total_cases": len(cases),
                    "passed_cases": 0,
                    "field_accuracy": {},
                    "extraction_score": 0.0,
                    "redaction_safety": 0.0,
                    "overall_score": 0.0,
                    "error": f"{name} provider not available — extraction not implemented",
                },
                "cases": [],
            }

    # Print per-provider summaries
    for name, report in reports.items():
        print(f"--- {name} ---")
        _print_summary(report)
        _print_per_field(report)
        if "error" in report["summary"]:
            print(f"  error: {report['summary']['error']}")

    # Delta report
    print()
    print("--- delta ---")
    local_score = reports["local"]["summary"]["overall_score"]
    sarvam_score = reports["sarvam"]["summary"]["overall_score"]
    delta = local_score - sarvam_score
    print(f"overall_score_local={local_score:.3f}")
    print(f"overall_score_sarvam={sarvam_score:.3f}")
    print(f"overall_score_delta={delta:+.3f}")

    # Per-field delta
    for field in reports["local"]["summary"].get("field_accuracy", {}):
        la = reports["local"]["summary"]["field_accuracy"].get(field, 0.0)
        sa = reports["sarvam"]["summary"]["field_accuracy"].get(field, 0.0)
        if la != sa:
            print(f"  {field}_delta={la - sa:+.3f}")

    if args.output:
        _write_report(
            Path(args.output),
            {
                "local": reports["local"],
                "sarvam": reports["sarvam"],
                "delta": {
                    "overall_score_local": local_score,
                    "overall_score_sarvam": sarvam_score,
                    "overall_score_delta": delta,
                },
            },
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bhasha-test")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser(
        "evaluate", help="Evaluate extraction/redaction fixtures"
    )
    evaluate.add_argument("fixture", help="Path to JSON or YAML fixture file")
    evaluate.add_argument(
        "--output", help="Optional path to write JSON report"
    )
    evaluate.add_argument(
        "--provider",
        choices=["local", "sarvam"],
        default="local",
        help="Provider to use for extraction (default: local)",
    )
    evaluate.add_argument(
        "--target",
        metavar="URL",
        help="HTTP target: POST cases to /evals/pipeline on a live API",
    )
    evaluate.set_defaults(func=evaluate_command)

    compare = subparsers.add_parser(
        "compare",
        help="Run both providers on the same fixture and compare",
    )
    compare.add_argument("fixture", help="Path to JSON or YAML fixture file")
    compare.add_argument(
        "--output", help="Optional path to write JSON delta report"
    )
    compare.set_defaults(func=compare_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
