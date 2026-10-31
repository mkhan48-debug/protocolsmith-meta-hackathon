import importlib.util
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_active_probe.py"
)
SPEC = importlib.util.spec_from_file_location(
    "protocolsmith_run_active_probe",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
run_active_probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = run_active_probe
SPEC.loader.exec_module(run_active_probe)


def proposal(
    legacy_parameter: str = "page_size",
    modern_parameter: str = "limit",
) -> run_active_probe.ProbeProposal:
    return run_active_probe.ProbeProposal(
        name="controlled_parameter_mapping_probe",
        hypothesis="Candidate page_size to limit mapping",
        customer_id="customer-123",
        legacy_parameter=legacy_parameter,
        modern_parameter=modern_parameter,
        value=1,
        information_gain="Cross-parameter controls distinguish names.",
    )


def controlled_request(
    base_url: str,
    customer_id: str,
    parameter: str | None,
    value: int | None,
    collection_field: str,
) -> dict[str, Any]:
    del customer_id, collection_field

    is_legacy = base_url == run_active_probe.LEGACY_BASE_URL
    correct_parameter = "page_size" if is_legacy else "limit"
    item_count = 1 if parameter == correct_parameter else 2

    return {
        "url": f"{base_url}/customers/customer-123/orders",
        "parameter": parameter,
        "value": value,
        "status_code": 200,
        "item_count": item_count,
        "body": {},
    }


def case_by_role(
    result: dict[str, Any],
    api: str,
    role: str,
) -> dict[str, Any]:
    return next(
        case
        for case in result["cases"]
        if case["api"] == api and case["role"] == role
    )


def supported_assessment() -> run_active_probe.ProbeAssessment:
    return run_active_probe.ProbeAssessment(
        hypothesis_supported=True,
        finding="All controlled outcomes support the candidate mapping.",
        discovered_mapping="page_size -> limit",
        confidence=0.95,
        recommended_next_probe="Test another endpoint.",
    )


def test_six_case_matrix_confirms_version_specific_mapping(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        run_active_probe,
        "perform_request",
        controlled_request,
    )

    result = run_active_probe.execute_probe(proposal())

    assert result["protocol"] == "six_case_cross_parameter_control_v1"
    assert len(result["cases"]) == 6
    assert result["deterministic_confirmation"] is True
    assert all(case["passed"] for case in result["cases"])
    assert all(check["passed"] for check in result["checks"])

    required_fields = {
        "api",
        "role",
        "parameter",
        "value",
        "url",
        "status_code",
        "item_count",
        "expected_item_count",
        "passed",
        "body",
    }
    assert all(
        required_fields <= case.keys() for case in result["cases"]
    )

    assert case_by_role(
        result,
        "legacy_v1",
        "baseline",
    )["item_count"] == 2
    assert case_by_role(
        result,
        "legacy_v1",
        "correct_parameter",
    )["item_count"] == 1
    assert case_by_role(
        result,
        "modern_v2",
        "wrong_parameter",
    )["item_count"] == 2


def test_probe_rejects_swapped_parameter_that_has_effect(
    monkeypatch,
) -> None:
    def wrong_name_has_effect(*args, **kwargs) -> dict[str, Any]:
        result = controlled_request(*args, **kwargs)
        base_url = args[0]
        parameter = args[2]
        if (
            base_url == run_active_probe.LEGACY_BASE_URL
            and parameter == "limit"
        ):
            result["item_count"] = 1
        return result

    monkeypatch.setattr(
        run_active_probe,
        "perform_request",
        wrong_name_has_effect,
    )

    result = run_active_probe.execute_probe(proposal())

    assert result["deterministic_confirmation"] is False
    assert case_by_role(
        result,
        "legacy_v1",
        "wrong_parameter",
    )["passed"] is False


def test_probe_rejects_same_parameter_name(monkeypatch) -> None:
    monkeypatch.setattr(
        run_active_probe,
        "perform_request",
        controlled_request,
    )

    result = run_active_probe.execute_probe(
        proposal(
            legacy_parameter="page_size",
            modern_parameter="page_size",
        )
    )

    assert result["deterministic_confirmation"] is False
    assert result["checks"][0] == {
        "name": "parameter names are version-specific",
        "passed": False,
    }


def test_probe_rejects_failed_or_unreadable_case(monkeypatch) -> None:
    def failed_case(*args, **kwargs) -> dict[str, Any]:
        result = controlled_request(*args, **kwargs)
        base_url = args[0]
        parameter = args[2]
        if (
            base_url == run_active_probe.MODERN_BASE_URL
            and parameter == "limit"
        ):
            result["status_code"] = 500
            result["item_count"] = None
        return result

    monkeypatch.setattr(
        run_active_probe,
        "perform_request",
        failed_case,
    )

    result = run_active_probe.execute_probe(proposal())

    assert result["deterministic_confirmation"] is False
    assert case_by_role(
        result,
        "modern_v2",
        "correct_parameter",
    )["passed"] is False


def test_muse_support_cannot_override_deterministic_failure() -> None:
    result = {"deterministic_confirmation": False}

    assert (
        run_active_probe.accept_probe(
            result,
            supported_assessment(),
        )
        is False
    )
