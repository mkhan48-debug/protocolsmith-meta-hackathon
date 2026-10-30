import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from protocolsmith_meta_hackathon.bridge_api import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIRECTORY = PROJECT_ROOT / "artifacts"
TEMPLATES_DIRECTORY = PROJECT_ROOT / "templates"

LAB_BASE_URL = os.getenv(
    "PROTOCOLSMITH_LAB_URL",
    "http://127.0.0.1:8000",
).rstrip("/")
BRIDGE_BASE_URL = os.getenv(
    "PROTOCOLSMITH_BRIDGE_URL",
    "http://127.0.0.1:8001",
).rstrip("/")

templates = Jinja2Templates(directory=str(TEMPLATES_DIRECTORY))


def read_artifact(filename: str) -> dict[str, Any]:
    path = ARTIFACTS_DIRECTORY / filename

    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def build_dashboard_context() -> dict[str, Any]:
    discovery = read_artifact("discovery_report.json")
    adapter = read_artifact("adapter_spec.json")
    active_trace = read_artifact("active_probe_trace.json")
    verification = read_artifact("verification_receipt.json")

    compatibility_plan = discovery.get(
        "compatibility_plan",
        {},
    )
    changes = compatibility_plan.get("changes", [])
    confidences = [
        float(change.get("confidence", 0))
        for change in changes
    ]

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0
    )

    verification_summary = verification.get("summary", {})
    adapter_spec = adapter.get("spec", {})

    return {
        "model": discovery.get("model", "muse-spark-1.3"),
        "summary": compatibility_plan.get("summary", ""),
        "experiment_count": len(discovery.get("evidence", [])),
        "change_count": len(changes),
        "changes": changes,
        "average_confidence": average_confidence,
        "verification_passed": verification_summary.get(
            "checks_passed",
            0,
        ),
        "verification_total": verification_summary.get(
            "checks_total",
            0,
        ),
        "checks": verification.get("checks", []),
        "known_loss": verification.get("known_loss", {}),
        "active_proposal": active_trace.get("proposal", {}),
        "active_assessment": active_trace.get("assessment", {}),
        "active_accepted": active_trace.get(
            "final_verdict",
            {},
        ).get("accepted", False),
        "query_rules": adapter_spec.get("query_rules", []),
        "item_rules": adapter_spec.get("item_field_rules", []),
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=build_dashboard_context(),
    )


def response_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    return {
        "url": str(response.request.url),
        "status_code": response.status_code,
        "body": body,
        "adapter": response.headers.get(
            "x-protocolsmith-adapter"
        ),
        "warning": response.headers.get(
            "x-protocolsmith-warning"
        ),
    }


@app.get("/api/live-proof")
async def live_proof():
    legacy_url = (
        f"{LAB_BASE_URL}/v1/customers/"
        "customer-123/orders"
    )
    modern_url = (
        f"{LAB_BASE_URL}/v2/customers/"
        "customer-123/orders"
    )
    bridge_url = (
        f"{BRIDGE_BASE_URL}/customers/"
        "customer-123/orders"
    )

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            legacy_response, modern_response, bridge_response = (
                await asyncio.gather(
                    client.get(
                        legacy_url,
                        params={"page_size": 1},
                    ),
                    client.get(
                        modern_url,
                        params={"page_size": 1},
                    ),
                    client.get(
                        bridge_url,
                        params={"page_size": 1},
                    ),
                )
            )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=503,
            content={
                "result": "unavailable",
                "message": (
                    "Start the laboratory on port 8000 and "
                    "the dashboard bridge on port 8001."
                ),
            },
        )

    legacy = response_payload(legacy_response)
    modern = response_payload(modern_response)
    bridge = response_payload(bridge_response)

    legacy_body = legacy["body"]
    modern_body = modern["body"]
    bridge_body = bridge["body"]

    legacy_compatible = (
        legacy["status_code"] == 200
        and isinstance(legacy_body, dict)
        and "orders" in legacy_body
    )
    modern_directly_incompatible = (
        modern["status_code"] == 200
        and isinstance(modern_body, dict)
        and "orders" not in modern_body
    )
    bridge_compatible = (
        bridge["status_code"] == 200
        and isinstance(bridge_body, dict)
        and "orders" in bridge_body
        and len(bridge_body["orders"]) == 1
    )

    overall_passed = (
        legacy_compatible
        and modern_directly_incompatible
        and bridge_compatible
    )

    return {
        "result": "passed" if overall_passed else "failed",
        "steps": {
            "legacy_v1": {
                "verdict": (
                    "pass" if legacy_compatible else "fail"
                ),
                **legacy,
            },
            "modern_v2_direct": {
                "verdict": (
                    "expected-failure"
                    if modern_directly_incompatible
                    else "unexpected"
                ),
                **modern,
            },
            "protocolsmith_bridge": {
                "verdict": (
                    "pass" if bridge_compatible else "fail"
                ),
                **bridge,
            },
        },
    }

