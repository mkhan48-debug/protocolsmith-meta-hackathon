import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((HOST, 0))
        return int(listener.getsockname()[1])


def wait_for_health(
    process: subprocess.Popen,
    url: str,
    timeout: float = 15.0,
) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"Server stopped before becoming ready: {url}"
            )

        try:
            response = httpx.get(url, timeout=0.5)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass

        time.sleep(0.1)

    raise AssertionError(f"Server did not become ready: {url}")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_short_command(
    arguments: list[str],
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_real_http_stack_restores_unchanged_client_contract(
    tmp_path: Path,
) -> None:
    lab_port = free_port()
    bridge_port = free_port()
    while bridge_port == lab_port:
        bridge_port = free_port()

    lab_url = f"http://{HOST}:{lab_port}"
    bridge_url = f"http://{HOST}:{bridge_port}"
    receipt_path = tmp_path / "verification_receipt.json"

    environment = os.environ.copy()
    environment.update(
        {
            "PROTOCOLSMITH_LEGACY_BASE_URL": f"{lab_url}/v1",
            "PROTOCOLSMITH_MODERN_BASE_URL": f"{lab_url}/v2",
            "PROTOCOLSMITH_LAB_URL": lab_url,
            "PROTOCOLSMITH_BRIDGE_URL": bridge_url,
            "PROTOCOLSMITH_RECEIPT_PATH": str(receipt_path),
        }
    )

    lab_process: subprocess.Popen | None = None
    bridge_process: subprocess.Popen | None = None

    try:
        lab_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "protocolsmith_meta_hackathon.lab_api:app",
                "--host",
                HOST,
                "--port",
                str(lab_port),
                "--log-level",
                "warning",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_health(lab_process, f"{lab_url}/health")

        bridge_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "protocolsmith_meta_hackathon.dashboard_api:app",
                "--host",
                HOST,
                "--port",
                str(bridge_port),
                "--log-level",
                "warning",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_health(bridge_process, f"{bridge_url}/health")

        legacy_client = [
            sys.executable,
            "scripts/legacy_client.py",
            "--base-url",
        ]

        legacy_result = run_short_command(
            [*legacy_client, f"{lab_url}/v1"],
            environment,
        )
        assert legacy_result.returncode == 0, legacy_result.stderr
        assert "Order order-1001" in legacy_result.stdout

        modern_result = run_short_command(
            [*legacy_client, f"{lab_url}/v2"],
            environment,
        )
        assert modern_result.returncode != 0
        assert "Legacy client failed" in (
            modern_result.stdout + modern_result.stderr
        )

        bridge_result = run_short_command(
            [*legacy_client, bridge_url],
            environment,
        )
        assert bridge_result.returncode == 0, bridge_result.stderr
        assert "Order order-1001" in bridge_result.stdout

        bridge_response = httpx.get(
            f"{bridge_url}/customers/customer-123/orders",
            params={"page_size": 1},
            timeout=5.0,
        )
        assert bridge_response.status_code == 200
        assert (
            bridge_response.headers["x-protocolsmith-adapter"]
            == "generated-spec"
        )
        assert bridge_response.json()["orders"][0]["id"] == "order-1001"

        verification = run_short_command(
            [sys.executable, "scripts/verify_bridge.py"],
            environment,
        )
        assert verification.returncode == 0, (
            verification.stdout + verification.stderr
        )
        assert receipt_path.exists()

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["result"] == "passed"
        assert receipt["summary"]["checks_total"] == 15
        assert (
            receipt["summary"]["checks_passed"]
            == receipt["summary"]["checks_total"]
        )
        assert any(
            check["name"] == "generated adapter identity disclosed"
            and check["passed"] is True
            for check in receipt["checks"]
        )
    finally:
        stop_process(bridge_process)
        stop_process(lab_process)
