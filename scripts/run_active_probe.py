import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

META_BASE_URL = "https://api.meta.ai/v1"
META_MODEL = "muse-spark-1.3"
LEGACY_BASE_URL = "http://127.0.0.1:8000/v1"
MODERN_BASE_URL = "http://127.0.0.1:8000/v2"
REPORT_PATH = Path("artifacts/discovery_report.json")
TRACE_PATH = Path("artifacts/active_probe_trace.json")


class ProbeProposal(BaseModel):
    name: str
    hypothesis: str
    customer_id: Literal["customer-123"]
    legacy_parameter: Literal[
        "page_size",
        "limit",
        "count",
        "per_page",
    ]
    modern_parameter: Literal[
        "page_size",
        "limit",
        "count",
        "per_page",
    ]
    value: Literal[1]
    information_gain: str


class ProbeAssessment(BaseModel):
    hypothesis_supported: bool
    finding: str
    discovered_mapping: str
    confidence: float
    recommended_next_probe: str


def load_report() -> dict[str, Any]:
    if not REPORT_PATH.exists():
        raise RuntimeError(
            "Discovery report is missing. Run discovery first."
        )

    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def create_meta_client() -> OpenAI:
    load_dotenv()

    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError("MODEL_API_KEY is missing from .env")

    return OpenAI(
        base_url=META_BASE_URL,
        api_key=api_key,
    )


def ask_muse_to_design_probe(
    client: OpenAI,
    report: dict[str, Any],
) -> ProbeProposal:
    system_prompt = """
You are ProtocolSmith's active experiment designer.

Your task is to select a controlled, discriminating experiment that
tests an inferred request-parameter mapping between a legacy API and
a modern API.

The controlled dataset contains exactly two records. A query value of
1 is therefore discriminating: the correct parameter returns one item,
while an ignored parameter leaves the default two-item result.

Choose parameter names only from the schema's allowlist.
Choose different legacy and modern parameter names.
The executor will run six controlled cases: a no-parameter baseline,
the proposed correct parameter, and the swapped parameter against each
API. The mapping is confirmed only when each correct name truncates to
one item while the baseline and swapped name both return two items.
Describe the mapping as a candidate hypothesis until those controls
pass.
Do not propose destructive requests.
Do not invent additional endpoints.
Explain why the experiment provides information rather than merely
repeating an observation.
"""

    context = {
        "summary": report["compatibility_plan"]["summary"],
        "changes": report["compatibility_plan"]["changes"],
        "unresolved_risks": report["compatibility_plan"][
            "unresolved_risks"
        ],
    }

    completion = client.beta.chat.completions.parse(
        model=META_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Design the highest-information request-parameter "
                    "experiment for this compatibility plan:\n\n"
                    + json.dumps(context, indent=2)
                ),
            },
        ],
        response_format=ProbeProposal,
    )

    proposal = completion.choices[0].message.parsed
    if proposal is None:
        raise RuntimeError("Muse did not return a probe proposal")

    return proposal


def perform_request(
    base_url: str,
    customer_id: str,
    parameter: str | None,
    value: int | None,
    collection_field: str,
) -> dict[str, Any]:
    params = (
        {parameter: value}
        if parameter is not None and value is not None
        else {}
    )

    response = httpx.get(
        f"{base_url}/customers/{customer_id}/orders",
        params=params,
        timeout=10.0,
    )

    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    item_count = None
    if isinstance(body, dict):
        collection = body.get(collection_field)
        if isinstance(collection, list):
            item_count = len(collection)

    return {
        "url": str(response.request.url),
        "parameter": parameter,
        "value": value,
        "status_code": response.status_code,
        "item_count": item_count,
        "body": body,
    }


def build_case(
    api: str,
    role: str,
    result: dict[str, Any],
    expected_item_count: int,
) -> dict[str, Any]:
    return {
        "api": api,
        "role": role,
        **result,
        "expected_item_count": expected_item_count,
        "passed": (
            result["status_code"] == 200
            and result["item_count"] == expected_item_count
        ),
    }


def execute_probe(
    proposal: ProbeProposal,
) -> dict[str, Any]:
    case_definitions = [
        (
            "legacy_v1",
            "baseline",
            LEGACY_BASE_URL,
            None,
            None,
            "orders",
            2,
        ),
        (
            "legacy_v1",
            "wrong_parameter",
            LEGACY_BASE_URL,
            proposal.modern_parameter,
            proposal.value,
            "orders",
            2,
        ),
        (
            "legacy_v1",
            "correct_parameter",
            LEGACY_BASE_URL,
            proposal.legacy_parameter,
            proposal.value,
            "orders",
            proposal.value,
        ),
        (
            "modern_v2",
            "baseline",
            MODERN_BASE_URL,
            None,
            None,
            "data",
            2,
        ),
        (
            "modern_v2",
            "wrong_parameter",
            MODERN_BASE_URL,
            proposal.legacy_parameter,
            proposal.value,
            "data",
            2,
        ),
        (
            "modern_v2",
            "correct_parameter",
            MODERN_BASE_URL,
            proposal.modern_parameter,
            proposal.value,
            "data",
            proposal.value,
        ),
    ]

    cases = [
        build_case(
            api,
            role,
            perform_request(
                base_url,
                proposal.customer_id,
                parameter,
                value,
                collection_field,
            ),
            expected_item_count,
        )
        for (
            api,
            role,
            base_url,
            parameter,
            value,
            collection_field,
            expected_item_count,
        ) in case_definitions
    ]

    checks = [
        {
            "name": "parameter names are version-specific",
            "passed": (
                proposal.legacy_parameter
                != proposal.modern_parameter
            ),
        },
        {
            "name": "all six requests returned HTTP 200",
            "passed": all(
                case["status_code"] == 200 for case in cases
            ),
        },
        {
            "name": "all six controlled counts matched",
            "passed": all(case["passed"] for case in cases),
        },
    ]

    return {
        "protocol": "six_case_cross_parameter_control_v1",
        "cases": cases,
        "checks": checks,
        "deterministic_confirmation": all(
            check["passed"] for check in checks
        ),
    }


def ask_muse_to_assess_probe(
    client: OpenAI,
    proposal: ProbeProposal,
    result: dict[str, Any],
) -> ProbeAssessment:
    system_prompt = """
You are ProtocolSmith's experiment assessor.

Evaluate whether the executed black-box experiment supports the
proposed request-parameter mapping.

The result contains six controlled cases. The candidate rename is
supported only when both no-parameter baselines return two items, the
legacy API returns one item only for the proposed legacy name, the
modern API returns one item only for the proposed modern name, each API
ignores the other version's parameter name, and all requests return
HTTP 200.

Base the conclusion only on the supplied request URLs, status codes,
and observed item counts. Do not mark the hypothesis supported if any
control fails. Do not claim certainty unsupported by the evidence.
Recommend a useful next experiment.
"""

    assessment_input = {
        "proposal": proposal.model_dump(),
        "result": result,
    }

    completion = client.beta.chat.completions.parse(
        model=META_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(assessment_input, indent=2),
            },
        ],
        response_format=ProbeAssessment,
    )

    assessment = completion.choices[0].message.parsed
    if assessment is None:
        raise RuntimeError("Muse did not assess the probe")

    return assessment


def accept_probe(
    result: dict[str, Any],
    assessment: ProbeAssessment,
) -> bool:
    return (
        result["deterministic_confirmation"]
        and assessment.hypothesis_supported
    )


def save_trace(
    proposal: ProbeProposal,
    result: dict[str, Any],
    assessment: ProbeAssessment,
) -> None:
    trace = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": META_MODEL,
        "mode": "active_model_designed_experiment",
        "proposal": proposal.model_dump(),
        "execution": result,
        "assessment": assessment.model_dump(),
        "final_verdict": {
            "deterministically_confirmed": result[
                "deterministic_confirmation"
            ],
            "model_supported": assessment.hypothesis_supported,
            "accepted": accept_probe(result, assessment),
        },
    }

    TRACE_PATH.write_text(
        json.dumps(trace, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    print("ProtocolSmith active discovery loop")
    print("1/4 Loading current evidence and uncertainty...")
    report = load_report()
    client = create_meta_client()

    print("2/4 Asking Muse Spark to design the next experiment...")
    proposal = ask_muse_to_design_probe(client, report)

    print(
        "Muse selected: "
        f"{proposal.legacy_parameter} -> "
        f"{proposal.modern_parameter}"
    )
    print(f"Hypothesis: {proposal.hypothesis}")

    print("3/4 Executing the model-designed experiment...")
    result = execute_probe(proposal)

    case_index = {
        (case["api"], case["role"]): case
        for case in result["cases"]
    }
    legacy_counts = [
        case_index[("legacy_v1", role)]["item_count"]
        for role in (
            "baseline",
            "wrong_parameter",
            "correct_parameter",
        )
    ]
    modern_counts = [
        case_index[("modern_v2", role)]["item_count"]
        for role in (
            "baseline",
            "wrong_parameter",
            "correct_parameter",
        )
    ]

    print(
        "Legacy counts (baseline/wrong/correct): "
        + "/".join(str(count) for count in legacy_counts)
    )
    print(
        "Modern counts (baseline/wrong/correct): "
        + "/".join(str(count) for count in modern_counts)
    )

    print("4/4 Asking Muse to assess the evidence...")
    assessment = ask_muse_to_assess_probe(
        client,
        proposal,
        result,
    )

    save_trace(proposal, result, assessment)

    accepted = accept_probe(result, assessment)

    print()
    print(f"Finding: {assessment.finding}")
    print(
        "Deterministic confirmation: "
        f"{result['deterministic_confirmation']}"
    )
    print(
        "Muse assessment supported: "
        f"{assessment.hypothesis_supported}"
    )
    print(f"Confidence: {assessment.confidence:.2f}")
    print(f"Trace saved to: {TRACE_PATH}")

    if not accepted:
        raise SystemExit(
            "The proposed mapping was not confirmed. "
            "Keep the trace and run a different probe."
        )

    print("Active experiment accepted")


if __name__ == "__main__":
    main()

