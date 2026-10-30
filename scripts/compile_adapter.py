import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

META_BASE_URL = "https://api.meta.ai/v1"
META_MODEL = "muse-spark-1.3"
REPORT_PATH = Path("artifacts/discovery_report.json")
SPEC_PATH = Path("artifacts/adapter_spec.json")


class QueryRule(BaseModel):
    legacy_name: str
    modern_name: str


class RootFieldRule(BaseModel):
    legacy_field: str
    modern_path: str
    operation: Literal["copy"]


class ItemFieldRule(BaseModel):
    legacy_field: str
    modern_path: str
    operation: Literal[
        "copy",
        "decimal_dollars_to_integer_cents",
        "date_to_iso_midnight_utc",
    ]


class ErrorRule(BaseModel):
    modern_indicator_path: str
    modern_indicator_value: str
    modern_customer_path: str
    legacy_status_code: int
    legacy_error_code: str
    legacy_error_message: str


class ExecutableAdapterSpec(BaseModel):
    query_rules: list[QueryRule]
    modern_collection_path: str
    legacy_collection_field: str
    root_field_rules: list[RootFieldRule]
    item_field_rules: list[ItemFieldRule]
    modern_pagination_path: str
    legacy_pagination_field: str
    error_rule: ErrorRule


def load_report() -> dict:
    if not REPORT_PATH.exists():
        raise RuntimeError(
            "Discovery report is missing. Run scripts/run_discovery.py first."
        )

    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def compile_with_muse(report: dict) -> ExecutableAdapterSpec:
    load_dotenv()

    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        raise RuntimeError("MODEL_API_KEY is missing from .env")

    client = OpenAI(
        base_url=META_BASE_URL,
        api_key=api_key,
    )

    system_prompt = """
You are ProtocolSmith's safe adapter compiler.

Convert the evidence-backed compatibility plan into a declarative,
machine-executable adapter specification.

The unchanged legacy client requires:
- query parameter: page_size
- response root fields: customer_id, orders, next_page
- each order requires: id, total_cents, created_at, status
- missing customers must appear as HTTP 404 with a legacy detail object

Rules:
- All modern paths must be dot-separated and relative to their object.
- Do not include "$", "[]", or the collection name in item paths.
- Root modern paths are relative to the modern response root.
- Item modern paths are relative to each modern collection item.
- Use only the transformation operations permitted by the schema.
- Map a modern YYYY-MM-DD date to legacy midnight UTC because the
  original time was lost and cannot be reconstructed.
- Map decimal dollar strings to integer cents deterministically.
- Do not invent unsupported mappings.
"""

    compiler_input = {
        "compatibility_plan": report["compatibility_plan"],
        "evidence": report["evidence"],
    }

    completion = client.beta.chat.completions.parse(
        model=META_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(compiler_input, indent=2),
            },
        ],
        response_format=ExecutableAdapterSpec,
    )

    spec = completion.choices[0].message.parsed
    if spec is None:
        raise RuntimeError("Muse did not return an executable adapter spec")

    return spec


def validate_spec(spec: ExecutableAdapterSpec) -> None:
    legacy_item_fields = {
        rule.legacy_field for rule in spec.item_field_rules
    }
    required_item_fields = {
        "id",
        "total_cents",
        "created_at",
        "status",
    }

    missing_item_fields = required_item_fields - legacy_item_fields
    if missing_item_fields:
        raise RuntimeError(
            f"Adapter spec is missing item fields: {missing_item_fields}"
        )

    query_mappings = {
        rule.legacy_name: rule.modern_name
        for rule in spec.query_rules
    }
    if "page_size" not in query_mappings:
        raise RuntimeError("Adapter spec does not map page_size")

    root_fields = {
        rule.legacy_field for rule in spec.root_field_rules
    }
    if "customer_id" not in root_fields:
        raise RuntimeError("Adapter spec does not map customer_id")

    if spec.legacy_collection_field != "orders":
        raise RuntimeError("Adapter spec must produce an orders collection")

    if spec.legacy_pagination_field != "next_page":
        raise RuntimeError("Adapter spec must produce next_page")


def save_spec(spec: ExecutableAdapterSpec) -> None:
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": META_MODEL,
        "source_report": str(REPORT_PATH),
        "spec": spec.model_dump(),
    }

    SPEC_PATH.write_text(
        json.dumps(artifact, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    print("ProtocolSmith safe adapter compiler")
    print("1/3 Loading the evidence-backed discovery report...")
    report = load_report()

    print("2/3 Asking Meta Muse Spark for a constrained adapter spec...")
    spec = compile_with_muse(report)

    print("3/3 Validating and saving the executable specification...")
    validate_spec(spec)
    save_spec(spec)

    print()
    print("Executable adapter specification created")
    print(f"Query rules: {len(spec.query_rules)}")
    print(f"Root rules: {len(spec.root_field_rules)}")
    print(f"Item rules: {len(spec.item_field_rules)}")
    print(f"Modern collection: {spec.modern_collection_path}")
    print(f"Legacy collection: {spec.legacy_collection_field}")

    for rule in spec.item_field_rules:
        print(
            f"- {rule.modern_path} -> {rule.legacy_field} "
            f"using {rule.operation}"
        )

    print(f"Specification saved to: {SPEC_PATH}")


if __name__ == "__main__":
    main()

