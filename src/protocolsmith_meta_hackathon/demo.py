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
PORT_SEARCH_LIMIT = 100


def port_is_free(port: int) -> bool:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as connection:
        try:
            connection.bind((HOST, port))
        except OSError:
            return False

    return True


def service_name(url: str) -> str | None:
    """Return the ProtocolSmith service name exposed by a health endpoint."""
    try:
        response = httpx.get(url, timeout=1)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    value = payload.get("service")
    return value if isinstance(value, str) else None


def existing_protocolsmith_is_ready(
    lab_url: str,
    dashboard_url: str,
) -> bool:
    """Check whether both default ports already host the complete demo."""
    return (
        service_name(f"{lab_url}/health") == "protocolsmith-lab"
        and service_name(f"{dashboard_url}/health") == "protocolsmith-bridge"
        and dashboard_is_ready(dashboard_url)
    )


def dashboard_is_ready(url: str) -> bool:
    """Reject a bare compatibility bridge that has no dashboard route."""
    try:
        response = httpx.get(url, timeout=1)
    except httpx.HTTPError:
        return False

    content_type = response.headers.get("content-type", "")
    return response.status_code == 200 and content_type.startswith("text/html")


def first_free_port(
    preferred: int,
    *,
    excluded: set[int] | None = None,
) -> int:
    """Choose a deterministic free localhost port near the preferred port."""
    excluded = excluded or set()

    candidates = [preferred]
    candidates.extend(
        range(
            max(LAB_PORT, preferred + 1),
            max(LAB_PORT, preferred + 1) + PORT_SEARCH_LIMIT,
        )
    )

    for candidate in candidates:
        if candidate not in excluded and port_is_free(candidate):
            return candidate

    raise RuntimeError(
        "ProtocolSmith could not find two available local ports. "
        "Stop an unused local server and try again."
    )


def choose_ports() -> tuple[int, int]:
    """Keep each service on its documented port whenever possible."""
    lab_port = LAB_PORT if port_is_free(LAB_PORT) else None
    dashboard_port = DASHBOARD_PORT if port_is_free(DASHBOARD_PORT) else None
    selected = {port for port in (lab_port, dashboard_port) if port is not None}
    alternate_port = max(LAB_PORT, DASHBOARD_PORT) + 1

    if lab_port is None:
        lab_port = first_free_port(
            alternate_port,
            excluded=selected,
        )
        selected.add(lab_port)

    if dashboard_port is None:
        dashboard_port = first_free_port(
            alternate_port,
            excluded=selected,
        )

    return lab_port, dashboard_port


def try_open_dashboard(url: str) -> bool:
    """Open a URL without leaking platform-launcher errors to the terminal."""
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["open", url],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return False

        return result.returncode == 0

    try:
        return webbrowser.open(url, new=2)
    except (webbrowser.Error, OSError):
        return False


def open_dashboard(url: str) -> None:
    """Open the demo when possible while always leaving a usable URL."""
    if os.getenv("PROTOCOLSMITH_NO_BROWSER", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        print("Automatic browser opening is disabled.")
        print(f"Open this URL manually: {url}")
        return

    opened = try_open_dashboard(url)

    if opened:
        print("Opened the dashboard in your default browser.")
    else:
        print("The browser did not open automatically.")
        print(f"Open this URL manually: {url}")


def wait_until_ready(
    name: str,
    url: str,
    process: subprocess.Popen,
    expected_service: str,
) -> None:
    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} stopped before becoming ready")

        if service_name(url) == expected_service:
            print(f"{name} is ready.")
            return

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
    default_lab_url = f"http://{HOST}:{LAB_PORT}"
    default_dashboard_url = f"http://{HOST}:{DASHBOARD_PORT}"

    if existing_protocolsmith_is_ready(
        default_lab_url,
        default_dashboard_url,
    ):
        print("ProtocolSmith is already running.")
        print(f"Laboratory: {default_lab_url}")
        print(f"Dashboard: {default_dashboard_url}")
        open_dashboard(default_dashboard_url)
        return

    try:
        lab_port, dashboard_port = choose_ports()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    lab_url = f"http://{HOST}:{lab_port}"
    dashboard_url = f"http://{HOST}:{dashboard_port}"

    if lab_port != LAB_PORT or dashboard_port != DASHBOARD_PORT:
        print(
            "The default ports are busy; ProtocolSmith will use "
            f"{lab_port} for the laboratory and {dashboard_port} "
            "for the dashboard instead."
        )

    environment = os.environ.copy()
    environment["PROTOCOLSMITH_LAB_URL"] = lab_url
    environment["PROTOCOLSMITH_BRIDGE_URL"] = dashboard_url
    environment["PROTOCOLSMITH_MODERN_BASE_URL"] = f"{lab_url}/v2"

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
                str(lab_port),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
        )

        wait_until_ready(
            "Controlled API laboratory",
            f"{lab_url}/health",
            lab_process,
            "protocolsmith-lab",
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
                str(dashboard_port),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
        )

        wait_until_ready(
            "Dashboard and compatibility bridge",
            f"{dashboard_url}/health",
            dashboard_process,
            "protocolsmith-bridge",
        )

        print()
        print("ProtocolSmith is ready.")
        print(f"Laboratory: {lab_url}")
        print(f"Dashboard: {dashboard_url}")
        print("Press Control+C once to stop everything.")
        print()

        open_dashboard(dashboard_url)

        while lab_process.poll() is None and dashboard_process.poll() is None:
            time.sleep(0.5)

        raise RuntimeError("A ProtocolSmith service stopped unexpectedly")

    except KeyboardInterrupt:
        print()
        print("Shutdown requested.")

    except RuntimeError as error:
        raise SystemExit(f"ProtocolSmith could not start: {error}") from None

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
