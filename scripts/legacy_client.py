import argparse

import httpx


def read_first_order(base_url: str, customer_id: str) -> str:
    response = httpx.get(
        f"{base_url}/customers/{customer_id}/orders",
        params={"page_size": 1},
        timeout=10.0,
    )
    response.raise_for_status()

    payload = response.json()
    first_order = payload["orders"][0]

    order_id = first_order["id"]
    total_dollars = first_order["total_cents"] / 100
    created_at = first_order["created_at"]
    status = first_order["status"]

    return (
        f"Order {order_id}: ${total_dollars:.2f}, "
        f"created {created_at}, status={status}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Unchanged legacy API client")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--customer-id", default="customer-123")
    args = parser.parse_args()

    try:
        result = read_first_order(args.base_url, args.customer_id)
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as error:
        raise SystemExit(
            f"Legacy client failed against {args.base_url}: {error}"
        ) from error

    print(result)


if __name__ == "__main__":
    main()

