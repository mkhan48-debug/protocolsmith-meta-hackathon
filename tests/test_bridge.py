import pytest

from protocolsmith_meta_hackathon.bridge_api import (
    AdapterError,
    adapt_item,
    adapt_success_response,
    apply_operation,
    build_modern_params,
    get_path,
    is_mapped_modern_error,
)


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

