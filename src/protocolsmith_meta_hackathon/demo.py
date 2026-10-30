import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
LAB_PORT = 8000
DASHBOARD_PORT = 8001


def port_is_free(port: int) -> bool:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as connection:
        return connection.connect_ex((HOST, port)) != 0


def wait_until_ready(
    name: str,
    url: str,
    process: subprocess.Popen,
) -> None:
    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"{name} stopped before becoming ready"
            )

        try:
            response = httpx.get(url, timeout=1)
            if response.status_code < 500:
                print(f"{name} is ready.")
                return
        except httpx.HTTPError:
            pass

        time.sleep(0.25)

    raise RuntimeError(f"{name} did not become ready")


def stop_process(
    name: str,
    process: subprocess.Popen | None,
) -> None:
    if process is None or process.poll() is not None:
        return

    print(f"Stopping {name}...")
    process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    for port in (LAB_PORT, DASHBOARD_PORT):
        if not port_is_free(port):
            raise SystemExit(
                f"Port {port} is already in use. "
                "Stop the old server and try again."
            )

    lab_url = f"http://{HOST}:{LAB_PORT}"
    dashboard_url = f"http://{HOST}:{DASHBOARD_PORT}"

    environment = os.environ.copy()
    environment["PROTOCOLSMITH_LAB_URL"] = lab_url
    environment["PROTOCOLSMITH_BRIDGE_URL"] = dashboard_url
    environment["PROTOCOLSMITH_MODERN_BASE_URL"] = (
        f"{lab_url}/v2"
    )

    lab_process = None
    dashboard_process = None

    try:
        print("Starting ProtocolSmith...")

        lab_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "protocolsmith_meta_hackathon.lab_api:app",
                "--host",
                HOST,
                "--port",
                str(LAB_PORT),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
        )

        wait_until_ready(
            "Controlled API laboratory",
            f"{lab_url}/health",
            lab_process,
        )

        dashboard_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "protocolsmith_meta_hackathon.dashboard_api:app",
                "--host",
                HOST,
                "--port",
                str(DASHBOARD_PORT),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
        )

        wait_until_ready(
            "Dashboard and compatibility bridge",
            f"{dashboard_url}/health",
            dashboard_process,
        )

        print()
        print("ProtocolSmith is ready.")
        print(f"Dashboard: {dashboard_url}")
        print("Press Control+C once to stop everything.")
        print()

        webbrowser.open(dashboard_url)

        while (
            lab_process.poll() is None
            and dashboard_process.poll() is None
        ):
            time.sleep(0.5)

        raise RuntimeError(
            "A ProtocolSmith service stopped unexpectedly"
        )

    except KeyboardInterrupt:
        print()
        print("Shutdown requested.")

    finally:
        stop_process(
            "dashboard and compatibility bridge",
            dashboard_process,
        )
        stop_process(
            "controlled API laboratory",
            lab_process,
        )
        print("ProtocolSmith stopped cleanly.")


if __name__ == "__main__":
    main()

