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
    parameter: str,
    value: int,
    collection_field: str,
) -> dict[str, Any]:
    response = httpx.get(
        f"{base_url}/customers/{customer_id}/orders",
        params={parameter: value},
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


def execute_probe(
    proposal: ProbeProposal,
) -> dict[str, Any]:
    legacy_result = perform_request(
        LEGACY_BASE_URL,
        proposal.customer_id,
        proposal.legacy_parameter,
        proposal.value,
        "orders",
    )

    modern_result = perform_request(
        MODERN_BASE_URL,
        proposal.customer_id,
        proposal.modern_parameter,
        proposal.value,
        "data",
    )

    deterministic_confirmation = (
        legacy_result["status_code"] == 200
        and modern_result["status_code"] == 200
        and legacy_result["item_count"] == proposal.value
        and modern_result["item_count"] == proposal.value
    )

    return {
        "legacy": legacy_result,
        "modern": modern_result,
        "deterministic_confirmation": deterministic_confirmation,
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

A parameter is behaviorally supported when applying value 1 causes
the corresponding API to return exactly one item from a dataset that
otherwise returns two items.

Base the conclusion only on the supplied request URLs, status codes,
and observed item counts. Do not claim certainty unsupported by the
evidence. Recommend a useful next experiment.
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
            "accepted": (
                result["deterministic_confirmation"]
                and assessment.hypothesis_supported
            ),
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

    print(
        "Observed item counts: "
        f"legacy={result['legacy']['item_count']}, "
        f"modern={result['modern']['item_count']}"
    )

    print("4/4 Asking Muse to assess the evidence...")
    assessment = ask_muse_to_assess_probe(
        client,
        proposal,
        result,
    )

    save_trace(proposal, result, assessment)

    accepted = (
        result["deterministic_confirmation"]
        and assessment.hypothesis_supported
    )

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

