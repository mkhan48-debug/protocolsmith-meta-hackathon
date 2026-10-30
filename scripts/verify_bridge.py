import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

LEGACY_BASE_URL = "http://127.0.0.1:8000/v1"
MODERN_BASE_URL = "http://127.0.0.1:8000/v2"
BRIDGE_BASE_URL = "http://127.0.0.1:8001"
RECEIPT_PATH = Path("artifacts/verification_receipt.json")


def fetch(
    base_url: str,
    customer_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = httpx.get(
        f"{base_url}/customers/{customer_id}/orders",
        params=params,
        timeout=10.0,
    )

    try:
        body: Any = response.json()
    except ValueError:
        body = response.text

    return {
        "url": str(response.request.url),
        "status_code": response.status_code,
        "body": body,
        "adapter_warning": response.headers.get(
            "x-protocolsmith-warning"
        ),
    }


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    evidence: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": passed,
            "evidence": evidence,
        }
    )


def main() -> None:
    print("ProtocolSmith deterministic contract verification")
    print("Collecting legacy, modern, and bridge responses...")

    legacy_one = fetch(
        LEGACY_BASE_URL,
        "customer-123",
        {"page_size": 1},
    )
    bridge_one = fetch(
        BRIDGE_BASE_URL,
        "customer-123",
        {"page_size": 1},
    )
    modern_direct = fetch(
        MODERN_BASE_URL,
        "customer-123",
        {"page_size": 1},
    )

    legacy_two = fetch(
        LEGACY_BASE_URL,
        "customer-123",
        {"page_size": 2},
    )
    bridge_two = fetch(
        BRIDGE_BASE_URL,
        "customer-123",
        {"page_size": 2},
    )

    legacy_missing = fetch(
        LEGACY_BASE_URL,
        "missing-customer",
        {"page_size": 1},
    )
    bridge_missing = fetch(
        BRIDGE_BASE_URL,
        "missing-customer",
        {"page_size": 1},
    )

    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "legacy API succeeds",
        legacy_one["status_code"] == 200,
        f"status={legacy_one['status_code']}",
    )
    add_check(
        checks,
        "modern API is directly incompatible",
        (
            modern_direct["status_code"] == 200
            and isinstance(modern_direct["body"], dict)
            and "orders" not in modern_direct["body"]
        ),
        "modern response intentionally has no legacy orders field",
    )
    add_check(
        checks,
        "bridge returns legacy success status",
        bridge_one["status_code"] == legacy_one["status_code"] == 200,
        (
            f"legacy={legacy_one['status_code']}, "
            f"bridge={bridge_one['status_code']}"
        ),
    )

    legacy_body = legacy_one["body"]
    bridge_body = bridge_one["body"]

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

    add_check(
        checks,
        "root customer identifier preserved",
        (
            isinstance(legacy_body, dict)
            and isinstance(bridge_body, dict)
            and legacy_body.get("customer_id")
            == bridge_body.get("customer_id")
        ),
        "customer_id values compared",
    )
    add_check(
        checks,
        "one-order collection size preserved",
        len(legacy_orders) == len(bridge_orders) == 1,
        (
            f"legacy_count={len(legacy_orders)}, "
            f"bridge_count={len(bridge_orders)}"
        ),
    )

    if legacy_orders and bridge_orders:
        legacy_order = legacy_orders[0]
        bridge_order = bridge_orders[0]

        for field in ("id", "total_cents", "status"):
            add_check(
                checks,
                f"order field preserved: {field}",
                legacy_order.get(field) == bridge_order.get(field),
                (
                    f"legacy={legacy_order.get(field)!r}, "
                    f"bridge={bridge_order.get(field)!r}"
                ),
            )

        legacy_date = str(legacy_order.get("created_at", ""))[:10]
        bridge_date = str(bridge_order.get("created_at", ""))[:10]

        add_check(
            checks,
            "created_at calendar date preserved",
            legacy_date == bridge_date,
            (
                f"legacy_date={legacy_date}, "
                f"bridge_date={bridge_date}"
            ),
        )

    legacy_two_orders = (
        legacy_two["body"].get("orders", [])
        if isinstance(legacy_two["body"], dict)
        else []
    )
    bridge_two_orders = (
        bridge_two["body"].get("orders", [])
        if isinstance(bridge_two["body"], dict)
        else []
    )

    add_check(
        checks,
        "page-size translation preserves two results",
        len(legacy_two_orders) == len(bridge_two_orders) == 2,
        (
            f"legacy_count={len(legacy_two_orders)}, "
            f"bridge_count={len(bridge_two_orders)}"
        ),
    )
    add_check(
        checks,
        "pagination value preserved",
        (
            isinstance(legacy_two["body"], dict)
            and isinstance(bridge_two["body"], dict)
            and legacy_two["body"].get("next_page")
            == bridge_two["body"].get("next_page")
        ),
        "next_page values compared",
    )
    add_check(
        checks,
        "missing-customer status restored",
        (
            legacy_missing["status_code"]
            == bridge_missing["status_code"]
            == 404
        ),
        (
            f"legacy={legacy_missing['status_code']}, "
            f"bridge={bridge_missing['status_code']}"
        ),
    )
    add_check(
        checks,
        "missing-customer error body restored",
        legacy_missing["body"] == bridge_missing["body"],
        "legacy and bridge error bodies compared exactly",
    )
    add_check(
        checks,
        "lossy date conversion disclosed",
        (
            isinstance(bridge_one["adapter_warning"], str)
            and "midnight UTC" in bridge_one["adapter_warning"]
        ),
        f"warning={bridge_one['adapter_warning']!r}",
    )

    passed = all(check["passed"] for check in checks)

    receipt = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "passed" if passed else "failed",
        "summary": {
            "checks_total": len(checks),
            "checks_passed": sum(
                1 for check in checks if check["passed"]
            ),
            "checks_failed": sum(
                1 for check in checks if not check["passed"]
            ),
        },
        "targets": {
            "legacy": LEGACY_BASE_URL,
            "modern": MODERN_BASE_URL,
            "bridge": BRIDGE_BASE_URL,
        },
        "checks": checks,
        "known_loss": {
            "field": "created_at",
            "reason": (
                "The modern API retains only the calendar date. "
                "ProtocolSmith reconstructs midnight UTC and exposes "
                "an explicit response warning."
            ),
        },
        "evidence": {
            "legacy_one": legacy_one,
            "modern_direct": modern_direct,
            "bridge_one": bridge_one,
            "legacy_two": legacy_two,
            "bridge_two": bridge_two,
            "legacy_missing": legacy_missing,
            "bridge_missing": bridge_missing,
        },
    }

    RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2),
        encoding="utf-8",
    )

    print()
    for check in checks:
        marker = "PASS" if check["passed"] else "FAIL"
        print(f"[{marker}] {check['name']}")

    print()
    print(
        f"Result: {receipt['summary']['checks_passed']}/"
        f"{receipt['summary']['checks_total']} checks passed"
    )
    print(f"Receipt saved to: {RECEIPT_PATH}")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

