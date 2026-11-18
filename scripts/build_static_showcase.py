"""Build the honest, serverless ProtocolSmith showcase for GitHub Pages."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIRECTORY = PROJECT_ROOT / "artifacts"
SCREENSHOTS_DIRECTORY = PROJECT_ROOT / "assets" / "screenshots"
TEMPLATES_DIRECTORY = PROJECT_ROOT / "templates"
DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "docs"

EVIDENCE_FILENAMES = (
    "active_probe_trace.json",
    "adapter_spec.json",
    "discovery_report.json",
    "verification_receipt.json",
)
SCREENSHOT_FILENAMES = (
    "protocolsmith-hero.jpg",
    "protocolsmith-live-proof.jpg",
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected a JSON object in {path}")
    return payload


def build_dashboard_context() -> dict[str, Any]:
    discovery = read_json(ARTIFACTS_DIRECTORY / "discovery_report.json")
    adapter = read_json(ARTIFACTS_DIRECTORY / "adapter_spec.json")
    active_trace = read_json(ARTIFACTS_DIRECTORY / "active_probe_trace.json")
    verification = read_json(ARTIFACTS_DIRECTORY / "verification_receipt.json")

    compatibility_plan = discovery.get("compatibility_plan", {})
    changes = compatibility_plan.get("changes", [])
    confidences = [
        float(change.get("confidence", 0))
        for change in changes
        if isinstance(change, dict)
    ]
    active_execution = active_trace.get("execution", {})
    active_cases = active_execution.get("cases", [])
    if not isinstance(active_cases, list):
        active_cases = []
    active_case_passed = sum(
        1
        for case in active_cases
        if isinstance(case, dict) and case.get("passed") is True
    )
    active_accepted = (
        active_trace.get("final_verdict", {}).get("accepted", False) is True
    )
    active_causally_confirmed = (
        active_accepted
        and active_execution.get("deterministic_confirmation") is True
        and len(active_cases) == 6
        and active_case_passed == len(active_cases)
    )
    verification_summary = verification.get("summary", {})
    model_identifier = discovery.get("model", "muse-spark-1.3")
    model_display_name = (
        "Muse Spark 1.3" if model_identifier == "muse-spark-1.3" else model_identifier
    )
    adapter_spec = adapter.get("spec", {})

    return {
        "model": model_identifier,
        "model_display_name": model_display_name,
        "summary": compatibility_plan.get("summary", ""),
        "experiment_count": len(discovery.get("evidence", [])),
        "change_count": len(changes),
        "changes": changes,
        "average_confidence": (
            sum(confidences) / len(confidences) if confidences else 0
        ),
        "verification_passed": verification_summary.get("checks_passed", 0),
        "verification_total": verification_summary.get("checks_total", 0),
        "checks": verification.get("checks", []),
        "known_loss": verification.get("known_loss", {}),
        "active_proposal": active_trace.get("proposal", {}),
        "active_assessment": active_trace.get("assessment", {}),
        "active_accepted": active_accepted,
        "active_causally_confirmed": active_causally_confirmed,
        "active_cases": active_cases,
        "active_case_passed": active_case_passed,
        "active_case_total": len(active_cases),
        "query_rules": adapter_spec.get("query_rules", []),
        "item_rules": adapter_spec.get("item_field_rules", []),
    }


def recorded_step(
    evidence: dict[str, Any],
    verdict: str,
) -> dict[str, Any]:
    return {
        "verdict": verdict,
        "url": evidence.get("url"),
        "status_code": evidence.get("status_code"),
        "body": evidence.get("body"),
        "adapter": evidence.get("adapter"),
        "warning": evidence.get("adapter_warning"),
    }


def build_recorded_proof(receipt: dict[str, Any]) -> dict[str, Any]:
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        raise TypeError("Verification receipt is missing its evidence object")

    required = {"legacy_one", "modern_direct", "bridge_one"}
    missing = required - evidence.keys()
    if missing:
        raise ValueError(
            "Verification receipt is missing evidence: " + ", ".join(sorted(missing))
        )

    return {
        "mode": "recorded-verification-replay",
        "recorded_at": receipt.get("generated_at"),
        "result": receipt.get("result"),
        "checks": receipt.get("checks", []),
        "steps": {
            "legacy_v1": recorded_step(evidence["legacy_one"], "pass"),
            "modern_v2_direct": recorded_step(
                evidence["modern_direct"],
                "expected-failure",
            ),
            "protocolsmith_bridge": recorded_step(
                evidence["bridge_one"],
                "pass",
            ),
        },
    }


def render_showcase(output_directory: Path) -> Path:
    receipt = read_json(ARTIFACTS_DIRECTORY / "verification_receipt.json")
    context = build_dashboard_context()
    context.update(
        {
            "static_showcase": True,
            "static_proof": build_recorded_proof(receipt),
            "static_generated_at": receipt.get("generated_at", "unknown"),
        }
    )

    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIRECTORY)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = environment.get_template("dashboard.html")
    rendered = template.render(**context)

    output_directory.mkdir(parents=True, exist_ok=True)
    evidence_directory = output_directory / "evidence"
    evidence_directory.mkdir(parents=True, exist_ok=True)
    assets_directory = output_directory / "assets"
    assets_directory.mkdir(parents=True, exist_ok=True)

    index_path = output_directory / "index.html"
    index_path.write_text(rendered, encoding="utf-8")
    (output_directory / ".nojekyll").write_text("", encoding="utf-8")

    for filename in EVIDENCE_FILENAMES:
        shutil.copyfile(
            ARTIFACTS_DIRECTORY / filename,
            evidence_directory / filename,
        )

    for filename in SCREENSHOT_FILENAMES:
        shutil.copyfile(
            SCREENSHOTS_DIRECTORY / filename,
            assets_directory / filename,
        )

    return index_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the static ProtocolSmith evidence showcase."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Destination directory (default: docs).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index_path = render_showcase(args.output_dir.resolve())
    print(f"Built static ProtocolSmith showcase: {index_path}")


if __name__ == "__main__":
    main()
