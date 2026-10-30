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


def evaluate_live_proof(
    legacy: dict[str, Any],
    modern: dict[str, Any],
    bridge: dict[str, Any],
    legacy_missing: dict[str, Any],
    bridge_missing: dict[str, Any],
) -> dict[str, Any]:
    legacy_body = legacy["body"]
    modern_body = modern["body"]
    bridge_body = bridge["body"]

    legacy_orders = (
        legacy_body.get("orders", [])
        if isinstance(legacy_body, dict)
        else []
    )
    bridge_orders = (
        bridge_body.get("orders", [])
        if isinstance(bridge_body, dict)
        else []
    )

    legacy_order = legacy_orders[0] if len(legacy_orders) == 1 else {}
    bridge_order = bridge_orders[0] if len(bridge_orders) == 1 else {}

    checks = {
        "legacy contract succeeds": (
            legacy["status_code"] == 200
            and len(legacy_orders) == 1
        ),
        "modern API is directly incompatible": (
            modern["status_code"] == 200
            and isinstance(modern_body, dict)
            and "orders" not in modern_body
        ),
        "bridge restores success status": bridge["status_code"] == 200,
        "bridge restores customer identifier": (
            isinstance(legacy_body, dict)
            and isinstance(bridge_body, dict)
            and legacy_body.get("customer_id")
            == bridge_body.get("customer_id")
        ),
        "bridge restores one-order collection": (
            len(legacy_orders) == len(bridge_orders) == 1
        ),
        "bridge preserves order id": (
            legacy_order.get("id") == bridge_order.get("id")
        ),
        "bridge preserves monetary value": (
            legacy_order.get("total_cents")
            == bridge_order.get("total_cents")
        ),
        "bridge preserves status": (
            legacy_order.get("status")
            == bridge_order.get("status")
        ),
        "bridge preserves calendar date": (
            str(legacy_order.get("created_at", ""))[:10]
            == str(bridge_order.get("created_at", ""))[:10]
        ),
        "bridge preserves pagination": (
            isinstance(legacy_body, dict)
            and isinstance(bridge_body, dict)
            and legacy_body.get("next_page")
            == bridge_body.get("next_page")
        ),
        "bridge discloses lossy reconstruction": (
            isinstance(bridge.get("warning"), str)
            and "midnight UTC" in bridge["warning"]
        ),
        "bridge restores missing-customer status": (
            legacy_missing["status_code"]
            == bridge_missing["status_code"]
            == 404
        ),
        "bridge restores missing-customer body": (
            legacy_missing["body"] == bridge_missing["body"]
        ),
    }

    return {
        "result": "passed" if all(checks.values()) else "failed",
        "checks": [
            {"name": name, "passed": passed}
            for name, passed in checks.items()
        ],
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
    legacy_missing_url = (
        f"{LAB_BASE_URL}/v1/customers/"
        "missing-customer/orders"
    )
    bridge_missing_url = (
        f"{BRIDGE_BASE_URL}/customers/"
        "missing-customer/orders"
    )

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            (
                legacy_response,
                modern_response,
                bridge_response,
                legacy_missing_response,
                bridge_missing_response,
            ) = (
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
                    client.get(
                        legacy_missing_url,
                        params={"page_size": 1},
                    ),
                    client.get(
                        bridge_missing_url,
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
    legacy_missing = response_payload(legacy_missing_response)
    bridge_missing = response_payload(bridge_missing_response)
    evaluation = evaluate_live_proof(
        legacy,
        modern,
        bridge,
        legacy_missing,
        bridge_missing,
    )

    return {
        "result": evaluation["result"],
        "checks": evaluation["checks"],
        "steps": {
            "legacy_v1": {
                "verdict": (
                    "pass"
                    if evaluation["checks"][0]["passed"]
                    else "fail"
                ),
                **legacy,
            },
            "modern_v2_direct": {
                "verdict": (
                    "expected-failure"
                    if evaluation["checks"][1]["passed"]
                    else "unexpected"
                ),
                **modern,
            },
            "protocolsmith_bridge": {
                "verdict": (
                    "pass"
                    if evaluation["result"] == "passed"
                    else "fail"
                ),
                **bridge,
            },
        },
    }

