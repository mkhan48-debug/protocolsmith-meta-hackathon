import pytest

import protocolsmith_meta_hackathon.dashboard_api as dashboard_api
from protocolsmith_meta_hackathon.bridge_api import (
    AdapterError,
    adapt_item,
    adapt_success_response,
    apply_operation,
    build_modern_params,
    get_path,
    is_mapped_modern_error,
)
from protocolsmith_meta_hackathon.dashboard_api import evaluate_live_proof


def modern_order() -> dict:
    return {
        "order_id": "order-1001",
        "amount": {
            "value": "25.99",
            "currency": "USD",
        },
        "created": "2026-10-20",
        "state": "paid",
    }


def modern_success() -> dict:
    return {
        "customer": {"id": "customer-123"},
        "data": [modern_order()],
        "pagination": {"next_cursor": None},
    }


def test_nested_path_lookup() -> None:
    assert get_path(modern_success(), "customer.id") == "customer-123"


def test_missing_path_is_rejected() -> None:
    with pytest.raises(AdapterError):
        get_path(modern_success(), "customer.missing")


def test_decimal_dollars_become_integer_cents() -> None:
    assert (
        apply_operation(
            "25.99",
            "decimal_dollars_to_integer_cents",
        )
        == 2599
    )


def test_date_becomes_midnight_utc() -> None:
    assert (
        apply_operation(
            "2026-10-20",
            "date_to_iso_midnight_utc",
        )
        == "2026-10-20T00:00:00Z"
    )


def test_query_parameter_is_translated() -> None:
    assert build_modern_params(2) == {"limit": 2}


def test_modern_item_becomes_legacy_item() -> None:
    assert adapt_item(modern_order()) == {
        "id": "order-1001",
        "status": "paid",
        "total_cents": 2599,
        "created_at": "2026-10-20T00:00:00Z",
    }


def test_modern_success_becomes_legacy_contract() -> None:
    assert adapt_success_response(modern_success()) == {
        "customer_id": "customer-123",
        "orders": [
            {
                "id": "order-1001",
                "status": "paid",
                "total_cents": 2599,
                "created_at": "2026-10-20T00:00:00Z",
            }
        ],
        "next_page": None,
    }


def test_modern_error_is_detected() -> None:
    body = {
        "data": [],
        "error": {
            "type": "unknown_customer",
            "customer": "missing-customer",
        },
    }
    assert is_mapped_modern_error(body) is True


def test_non_usd_currency_fails_closed() -> None:
    item = modern_order()
    item["amount"]["currency"] = "EUR"

    with pytest.raises(AdapterError):
        adapt_item(item)


def proof_response(
    body: dict,
    status_code: int = 200,
    warning: str | None = None,
    adapter: str | None = None,
) -> dict:
    return {
        "url": "http://example.test",
        "status_code": status_code,
        "body": body,
        "adapter": adapter,
        "warning": warning,
    }


def test_live_proof_requires_full_contract_equivalence() -> None:
    legacy = proof_response(
        {
            "customer_id": "customer-123",
            "orders": [
                {
                    "id": "order-1001",
                    "total_cents": 2599,
                    "created_at": "2026-10-20T14:30:00Z",
                    "status": "paid",
                }
            ],
            "next_page": None,
        }
    )
    modern = proof_response({"data": [modern_order()]})
    bridge = proof_response(
        {
            "customer_id": "customer-123",
            "orders": [
                {
                    "id": "order-1001",
                    "total_cents": 2599,
                    "created_at": "2026-10-20T00:00:00Z",
                    "status": "paid",
                }
            ],
            "next_page": None,
        },
        warning="created_at reconstructed at midnight UTC",
        adapter="generated-spec",
    )
    missing_body = {
        "detail": {
            "code": "CUSTOMER_NOT_FOUND",
            "message": "Customer does not exist",
        }
    }

    evaluation = evaluate_live_proof(
        legacy,
        modern,
        bridge,
        proof_response(missing_body, status_code=404),
        proof_response(missing_body, status_code=404),
    )

    assert evaluation["result"] == "passed"
    assert all(check["passed"] for check in evaluation["checks"])


def test_live_proof_rejects_wrong_bridge_value() -> None:
    legacy = proof_response(
        {
            "customer_id": "customer-123",
            "orders": [
                {
                    "id": "order-1001",
                    "total_cents": 2599,
                    "created_at": "2026-10-20T14:30:00Z",
                    "status": "paid",
                }
            ],
            "next_page": None,
        }
    )
    bridge = proof_response(
        {
            "customer_id": "customer-123",
            "orders": [
                {
                    "id": "order-1001",
                    "total_cents": 1,
                    "created_at": "2026-10-20T00:00:00Z",
                    "status": "paid",
                }
            ],
            "next_page": None,
        },
        warning="created_at reconstructed at midnight UTC",
        adapter="generated-spec",
    )
    missing_body = {
        "detail": {
            "code": "CUSTOMER_NOT_FOUND",
            "message": "Customer does not exist",
        }
    }

    evaluation = evaluate_live_proof(
        legacy,
        proof_response({"data": [modern_order()]}),
        bridge,
        proof_response(missing_body, status_code=404),
        proof_response(missing_body, status_code=404),
    )

    assert evaluation["result"] == "failed"
    assert any(
        check["name"] == "bridge preserves monetary value"
        and not check["passed"]
        for check in evaluation["checks"]
    )


def test_live_proof_rejects_missing_adapter_identity() -> None:
    legacy_body = {
        "customer_id": "customer-123",
        "orders": [
            {
                "id": "order-1001",
                "total_cents": 2599,
                "created_at": "2026-10-20T14:30:00Z",
                "status": "paid",
            }
        ],
        "next_page": None,
    }
    bridge_body = {
        "customer_id": "customer-123",
        "orders": [
            {
                "id": "order-1001",
                "total_cents": 2599,
                "created_at": "2026-10-20T00:00:00Z",
                "status": "paid",
            }
        ],
        "next_page": None,
    }
    missing_body = {
        "detail": {
            "code": "CUSTOMER_NOT_FOUND",
            "message": "Customer does not exist",
        }
    }

    evaluation = evaluate_live_proof(
        proof_response(legacy_body),
        proof_response({"data": [modern_order()]}),
        proof_response(
            bridge_body,
            warning="created_at reconstructed at midnight UTC",
        ),
        proof_response(missing_body, status_code=404),
        proof_response(missing_body, status_code=404),
    )

    assert evaluation["result"] == "failed"
    assert any(
        check["name"] == "bridge identifies generated adapter"
        and not check["passed"]
        for check in evaluation["checks"]
    )


def dashboard_artifact_reader(active_trace: dict):
    def read_artifact(filename: str) -> dict:
        if filename == "active_probe_trace.json":
            return active_trace
        if filename == "discovery_report.json":
            return {
                "model": "muse-spark-1.3",
                "evidence": [],
                "compatibility_plan": {"changes": []},
            }
        if filename == "adapter_spec.json":
            return {"spec": {}}
        if filename == "verification_receipt.json":
            return {"summary": {}, "checks": []}
        return {}

    return read_artifact


def test_old_active_artifact_is_not_called_causally_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_trace = {
        "execution": {"deterministic_confirmation": True},
        "final_verdict": {"accepted": True},
    }
    monkeypatch.setattr(
        dashboard_api,
        "read_artifact",
        dashboard_artifact_reader(old_trace),
    )

    context = dashboard_api.build_dashboard_context()

    assert context["active_accepted"] is True
    assert context["active_case_total"] == 0
    assert context["active_causally_confirmed"] is False


def test_six_passing_controls_are_called_causally_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controlled_trace = {
        "execution": {
            "deterministic_confirmation": True,
            "cases": [
                {"api": "legacy_v1", "role": role, "passed": True}
                for role in ("baseline", "wrong_parameter", "correct_parameter")
            ]
            + [
                {"api": "modern_v2", "role": role, "passed": True}
                for role in ("baseline", "wrong_parameter", "correct_parameter")
            ],
        },
        "final_verdict": {"accepted": True},
    }
    monkeypatch.setattr(
        dashboard_api,
        "read_artifact",
        dashboard_artifact_reader(controlled_trace),
    )

    context = dashboard_api.build_dashboard_context()

    assert context["active_case_passed"] == 6
    assert context["active_case_total"] == 6
    assert context["active_causally_confirmed"] is True

