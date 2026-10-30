import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

LEGACY_BASE_URL = "http://127.0.0.1:8000/v1"
MODERN_BASE_URL = "http://127.0.0.1:8000/v2"
META_BASE_URL = "https://api.meta.ai/v1"
META_MODEL = "muse-spark-1.3"


class CompatibilityChange(BaseModel):
    category: str
    legacy_path: str
    modern_path: str
    transformation: str
    evidence: str
    confidence: float


class CompatibilityPlan(BaseModel):
    summary: str
    changes: list[CompatibilityChange]
    error_semantics: str
    verification_strategy: list[str]
    unresolved_risks: list[str]


def describe_shape(value: Any, path: str = "$") -> list[dict[str, Any]]:
    descriptions: list[dict[str, Any]] = []

    if isinstance(value, dict):
        descriptions.append({"path": path, "type": "object"})
        for key in sorted(value):
            descriptions.extend(describe_shape(value[key], f"{path}.{key}"))
        return descriptions

    if isinstance(value, list):
        descriptions.append(
            {
                "path": path,
                "type": "array",
                "length": len(value),
            }
        )
        if value:
            descriptions.extend(describe_shape(value[0], f"{path}[]"))
        return descriptions

    descriptions.append(
        {
            "path": path,
            "type": type(value).__name__,
            "example": value,
        }
    )
    return descriptions


def probe(
    base_url: str,
    customer_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    url = f"{base_url}/customers/{customer_id}/orders"

    response = httpx.get(
        url,
        params=params,
        timeout=10.0,
    )

    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    return {
        "request": {
            "method": "GET",
            "url": str(response.request.url),
            "customer_id": customer_id,
            "params": params,
        },
        "response": {
            "status_code": response.status_code,
            "body": body,
            "shape": describe_shape(body),
        },
    }


def collect_evidence() -> list[dict[str, Any]]:
    experiments = [
        {
            "name": "one_existing_order",
            "customer_id": "customer-123",
            "legacy_params": {"page_size": 1},
            "modern_params": {"limit": 1},
            "purpose": "Compare one successful result.",
        },
        {
            "name": "two_existing_orders",
            "customer_id": "customer-123",
            "legacy_params": {"page_size": 2},
            "modern_params": {"limit": 2},
            "purpose": "Reveal pagination and repeated item structure.",
        },
        {
            "name": "missing_customer",
            "customer_id": "missing-customer",
            "legacy_params": {"page_size": 1},
            "modern_params": {"limit": 1},
            "purpose": "Compare error status and error-body semantics.",
        },
    ]

    evidence: list[dict[str, Any]] = []

    for experiment in experiments:
        print(f"  Running experiment: {experiment['name']}")

        legacy_result = probe(
            LEGACY_BASE_URL,
            experiment["customer_id"],
            experiment["legacy_params"],
        )
        modern_result = probe(
            MODERN_BASE_URL,
            experiment["customer_id"],
            experiment["modern_params"],
        )

        evidence.append(
            {
                "experiment": experiment["name"],
                "purpose": experiment["purpose"],
                "legacy": legacy_result,
                "modern": modern_result,
            }
        )

    return evidence


def ask_muse_for_plan(
    evidence: list[dict[str, Any]],
) -> CompatibilityPlan:
    load_dotenv()

    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError("MODEL_API_KEY is missing from .env")

    client = OpenAI(
        base_url=META_BASE_URL,
        api_key=api_key,
    )

    system_prompt = """
You are ProtocolSmith, an active API-archaeology agent.

You receive paired observations from a legacy API and a modern API.
Infer only compatibility changes that are supported by the evidence.

Identify:
- request parameter renames,
- response field and nesting changes,
- deterministic value transformations,
- pagination changes,
- HTTP status and error-semantics changes.

Use precise JSONPath-like paths such as $.orders[].id.
Describe transformations so they can become executable adapter code.
Do not invent fields that are absent from the observations.
Confidence must be a number between 0 and 1.
"""

    user_prompt = (
        "Analyze these controlled API experiments and produce the "
        "compatibility plan:\n\n"
        + json.dumps(evidence, indent=2)
    )

    completion = client.beta.chat.completions.parse(
        model=META_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=CompatibilityPlan,
    )

    plan = completion.choices[0].message.parsed
    if plan is None:
        raise RuntimeError("Muse did not return a compatibility plan")

    return plan


def save_report(
    evidence: list[dict[str, Any]],
    plan: CompatibilityPlan,
) -> Path:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": META_MODEL,
        "legacy_base_url": LEGACY_BASE_URL,
        "modern_base_url": MODERN_BASE_URL,
        "evidence": evidence,
        "compatibility_plan": plan.model_dump(),
    }

    output_directory = Path("artifacts")
    output_directory.mkdir(exist_ok=True)

    output_path = output_directory / "discovery_report.json"
    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    return output_path


def main() -> None:
    print("ProtocolSmith discovery run")
    print("1/3 Collecting controlled differential evidence...")
    evidence = collect_evidence()

    print("2/3 Asking Meta Muse Spark to infer compatibility rules...")
    plan = ask_muse_for_plan(evidence)

    print("3/3 Saving the evidence and compatibility plan...")
    output_path = save_report(evidence, plan)

    print()
    print("Discovery complete")
    print(f"Summary: {plan.summary}")
    print(f"Changes discovered: {len(plan.changes)}")

    for number, change in enumerate(plan.changes, start=1):
        print(
            f"{number}. [{change.category}] "
            f"{change.legacy_path} -> {change.modern_path}"
        )
        print(f"   Transform: {change.transformation}")
        print(f"   Confidence: {change.confidence:.2f}")

    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()

