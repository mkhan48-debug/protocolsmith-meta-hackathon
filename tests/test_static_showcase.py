import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "build_static_showcase.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_static_showcase",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
build_static_showcase = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_static_showcase)


def test_recorded_proof_uses_committed_receipt() -> None:
    receipt = build_static_showcase.read_json(
        build_static_showcase.ARTIFACTS_DIRECTORY / "verification_receipt.json"
    )

    proof = build_static_showcase.build_recorded_proof(receipt)

    assert proof["mode"] == "recorded-verification-replay"
    assert proof["result"] == "passed"
    assert len(proof["checks"]) == 15
    assert all(check["passed"] for check in proof["checks"])
    assert proof["steps"]["legacy_v1"]["verdict"] == "pass"
    assert proof["steps"]["modern_v2_direct"]["verdict"] == "expected-failure"
    assert proof["steps"]["protocolsmith_bridge"]["verdict"] == "pass"


def test_static_showcase_is_serverless_and_honestly_labeled(
    tmp_path: Path,
) -> None:
    index_path = build_static_showcase.render_showcase(tmp_path)
    html = index_path.read_text(encoding="utf-8")

    assert "/api/live-proof" not in html
    assert "Replay recorded verification" in html
    assert "The recorded verification replay." in html
    assert "does not run a backend or make live API requests" in html
    assert "Run the live proof locally" in html
    assert "15/15" in html
    assert "recorded-verification-replay" in html
    assert "https://github.com/mkhan48-debug/protocolsmith-meta-hackathon" in html

    evidence_directory = tmp_path / "evidence"
    assets_directory = tmp_path / "assets"
    assert (tmp_path / ".nojekyll").exists()
    assert {path.name for path in evidence_directory.iterdir()} == set(
        build_static_showcase.EVIDENCE_FILENAMES
    )
    assert {path.name for path in assets_directory.iterdir()} == set(
        build_static_showcase.SCREENSHOT_FILENAMES
    )

    copied_receipt = json.loads(
        (evidence_directory / "verification_receipt.json").read_text(encoding="utf-8")
    )
    assert copied_receipt["summary"] == {
        "checks_total": 15,
        "checks_passed": 15,
        "checks_failed": 0,
    }
