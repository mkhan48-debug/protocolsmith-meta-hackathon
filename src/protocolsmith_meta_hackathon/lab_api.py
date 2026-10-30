from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

app = FastAPI(
    title="ProtocolSmith Controlled API Laboratory",
    description="Two intentionally incompatible API versions.",
)

legacy_api = FastAPI(title="Legacy Orders API")
modern_api = FastAPI(title="Modern Orders API")

ORDERS = {
    "customer-123": [
        {
            "id": "order-1001",
            "total_cents": 2599,
            "created_at": "2026-10-20T14:30:00Z",
            "status": "paid",
        },
        {
            "id": "order-1002",
            "total_cents": 1099,
            "created_at": "2026-10-21T09:15:00Z",
            "status": "shipped",
        },
    ]
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "protocolsmith-lab"}


@legacy_api.get("/customers/{customer_id}/orders")
def legacy_orders(
    customer_id: str,
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict:
    if customer_id not in ORDERS:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CUSTOMER_NOT_FOUND",
                "message": "Customer does not exist",
            },
        )

    orders = ORDERS[customer_id][:page_size]
    return {
        "customer_id": customer_id,
        "orders": orders,
        "next_page": None,
    }


@modern_api.get("/customers/{customer_id}/orders")
def modern_orders(
    customer_id: str,
    limit: int = Query(default=10, ge=1, le=100),
):
    if customer_id not in ORDERS:
        return JSONResponse(
            status_code=200,
            content={
                "data": [],
                "error": {
                    "type": "unknown_customer",
                    "customer": customer_id,
                },
            },
        )

    orders = ORDERS[customer_id][:limit]
    return {
        "customer": {"id": customer_id},
        "data": [
            {
                "order_id": order["id"],
                "amount": {
                    "value": f"{order['total_cents'] / 100:.2f}",
                    "currency": "USD",
                },
                "created": order["created_at"][:10],
                "state": order["status"],
            }
            for order in orders
        ],
        "pagination": {"next_cursor": None},
    }


app.mount("/v1", legacy_api)
app.mount("/v2", modern_api)

