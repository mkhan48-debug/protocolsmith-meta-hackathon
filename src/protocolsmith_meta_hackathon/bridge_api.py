import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

SPEC_PATH = Path(
    os.getenv(
        "PROTOCOLSMITH_ADAPTER_SPEC",
        "artifacts/adapter_spec.json",
    )
)
MODERN_BASE_URL = os.getenv(
    "PROTOCOLSMITH_MODERN_BASE_URL",
    "http://127.0.0.1:8000/v2",
).rstrip("/")
MAX_RESPONSE_BYTES = 1_000_000


class AdapterError(RuntimeError):
    pass


def load_adapter_artifact() -> tuple[dict[str, Any], dict[str, Any]]:
    if not SPEC_PATH.exists():
        raise RuntimeError(
            f"Adapter specification does not exist: {SPEC_PATH}"
        )

    artifact = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    spec = artifact.get("spec")

    if not isinstance(spec, dict):
        raise RuntimeError("Adapter artifact does not contain a valid spec")

    return artifact, spec


def validate_target_url() -> None:
    parsed = urlparse(MODERN_BASE_URL)

    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError("Modern API URL must use HTTP or HTTPS")

    allowed_remote = os.getenv("PROTOCOLSMITH_ALLOW_REMOTE") == "1"
    local_hosts = {"127.0.0.1", "localhost"}

    if parsed.hostname not in local_hosts and not allowed_remote:
        raise RuntimeError(
            "Remote target blocked. Set PROTOCOLSMITH_ALLOW_REMOTE=1 "
            "only for a trusted API."
        )


ARTIFACT, SPEC = load_adapter_artifact()
validate_target_url()

app = FastAPI(
    title="ProtocolSmith Compatibility Bridge",
    description=(
        "Executes a constrained adapter specification generated from "
        "black-box differential evidence."
    ),
)


def get_path(payload: Any, path: str) -> Any:
    current = payload

    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise AdapterError(f"Required modern path is missing: {path}")
        current = current[segment]

    return current


def apply_operation(value: Any, operation: str) -> Any:
    if operation == "copy":
        return value

    if operation == "decimal_dollars_to_integer_cents":
        try:
            dollars = Decimal(str(value))
        except InvalidOperation as error:
            raise AdapterError(
                f"Invalid decimal money value: {value!r}"
            ) from error

        cents = (dollars * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
        return int(cents)

    if operation == "date_to_iso_midnight_utc":
        try:
            parsed_date = date.fromisoformat(str(value))
        except ValueError as error:
            raise AdapterError(
                f"Invalid modern date value: {value!r}"
            ) from error

        return f"{parsed_date.isoformat()}T00:00:00Z"

    raise AdapterError(f"Unsupported adapter operation: {operation}")


def ensure_supported_currency(
    modern_item: dict[str, Any],
    modern_value_path: str,
) -> None:
    if "." not in modern_value_path:
        raise AdapterError(
            "Money conversion requires a nested currency field"
        )

    parent_path = modern_value_path.rsplit(".", 1)[0]
    currency_path = f"{parent_path}.currency"
    currency = get_path(modern_item, currency_path)

    if currency != "USD":
        raise AdapterError(
            f"Unsupported currency {currency!r}; expected 'USD'"
        )


def adapt_item(modern_item: Any) -> dict[str, Any]:
    if not isinstance(modern_item, dict):
        raise AdapterError("Modern collection contains a non-object item")

    legacy_item: dict[str, Any] = {}

    for rule in SPEC["item_field_rules"]:
        modern_path = rule["modern_path"]
        operation = rule["operation"]
        value = get_path(modern_item, modern_path)

        if operation == "decimal_dollars_to_integer_cents":
            ensure_supported_currency(modern_item, modern_path)

        legacy_item[rule["legacy_field"]] = apply_operation(
            value,
            operation,
        )

    return legacy_item


def is_mapped_modern_error(modern_body: Any) -> bool:
    rule = SPEC["error_rule"]

    try:
        indicator = get_path(
            modern_body,
            rule["modern_indicator_path"],
        )
    except AdapterError:
        return False

    return indicator == rule["modern_indicator_value"]


def build_modern_params(page_size: int) -> dict[str, Any]:
    legacy_params = {"page_size": page_size}
    modern_params: dict[str, Any] = {}

    for rule in SPEC["query_rules"]:
        legacy_name = rule["legacy_name"]
        modern_name = rule["modern_name"]

        if legacy_name in legacy_params:
            modern_params[modern_name] = legacy_params[legacy_name]

    if not modern_params:
        raise AdapterError("No request parameters could be translated")

    return modern_params


def adapt_success_response(modern_body: Any) -> dict[str, Any]:
    if not isinstance(modern_body, dict):
        raise AdapterError("Modern response is not a JSON object")

    legacy_body: dict[str, Any] = {}

    for rule in SPEC["root_field_rules"]:
        value = get_path(modern_body, rule["modern_path"])
        legacy_body[rule["legacy_field"]] = apply_operation(
            value,
            rule["operation"],
        )

    modern_collection = get_path(
        modern_body,
        SPEC["modern_collection_path"],
    )
    if not isinstance(modern_collection, list):
        raise AdapterError("Modern collection is not an array")

    legacy_body[SPEC["legacy_collection_field"]] = [
        adapt_item(item) for item in modern_collection
    ]

    legacy_body[SPEC["legacy_pagination_field"]] = get_path(
        modern_body,
        SPEC["modern_pagination_path"],
    )

    return legacy_body


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "protocolsmith-bridge",
        "source_model": ARTIFACT.get("model"),
        "spec_loaded": True,
        "modern_target": MODERN_BASE_URL,
    }


@app.get("/spec")
def show_spec() -> dict[str, Any]:
    return {
        "model": ARTIFACT.get("model"),
        "generated_at": ARTIFACT.get("generated_at"),
        "spec": SPEC,
    }


@app.get("/customers/{customer_id}/orders")
def compatible_orders(
    customer_id: str,
    page_size: int = Query(default=10, ge=1, le=100),
):
    try:
        modern_params = build_modern_params(page_size)
    except AdapterError as error:
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "INVALID_ADAPTER", "message": str(error)}},
        )

    modern_url = (
        f"{MODERN_BASE_URL}/customers/{customer_id}/orders"
    )

    try:
        response = httpx.get(
            modern_url,
            params=modern_params,
            timeout=10.0,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=502,
            content={
                "detail": {
                    "code": "MODERN_API_UNAVAILABLE",
                    "message": "The modern API could not be reached",
                }
            },
        )

    if len(response.content) > MAX_RESPONSE_BYTES:
        return JSONResponse(
            status_code=502,
            content={
                "detail": {
                    "code": "MODERN_RESPONSE_TOO_LARGE",
                    "message": "The modern API response exceeded the safety limit",
                }
            },
        )

    try:
        modern_body = response.json()
    except ValueError:
        return JSONResponse(
            status_code=502,
            content={
                "detail": {
                    "code": "INVALID_MODERN_RESPONSE",
                    "message": "The modern API did not return JSON",
                }
            },
        )

    try:
        if is_mapped_modern_error(modern_body):
            error_rule = SPEC["error_rule"]
            observed_customer = get_path(
                modern_body,
                error_rule["modern_customer_path"],
            )

            if observed_customer != customer_id:
                raise AdapterError(
                    "Modern error references a different customer"
                )

            return JSONResponse(
                status_code=error_rule["legacy_status_code"],
                content={
                    "detail": {
                        "code": error_rule["legacy_error_code"],
                        "message": error_rule["legacy_error_message"],
                    }
                },
                headers={
                    "X-ProtocolSmith-Adapter": "generated-spec",
                },
            )

        if response.status_code >= 400:
            raise AdapterError(
                f"Unexpected modern status code: {response.status_code}"
            )

        legacy_body = adapt_success_response(modern_body)

    except AdapterError as error:
        return JSONResponse(
            status_code=502,
            content={
                "detail": {
                    "code": "ADAPTER_REJECTED_RESPONSE",
                    "message": str(error),
                }
            },
        )

    return JSONResponse(
        status_code=200,
        content=legacy_body,
        headers={
            "X-ProtocolSmith-Adapter": "generated-spec",
            "X-ProtocolSmith-Warning": (
                "created_at reconstructed at midnight UTC because "
                "the modern API discarded the original time"
            ),
        },
    )

