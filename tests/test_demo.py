from unittest.mock import Mock

import httpx

from protocolsmith_meta_hackathon import demo


def test_service_name_reads_protocolsmith_health(monkeypatch):
    request = httpx.Request("GET", "http://127.0.0.1:8000/health")
    response = httpx.Response(
        200,
        request=request,
        json={"service": "protocolsmith-lab"},
    )
    monkeypatch.setattr(demo.httpx, "get", Mock(return_value=response))

    assert demo.service_name(str(request.url)) == "protocolsmith-lab"


def test_service_name_rejects_unrelated_or_unavailable_service(monkeypatch):
    request = httpx.Request("GET", "http://127.0.0.1:8000/health")
    unrelated = httpx.Response(
        200,
        request=request,
        json={"status": "healthy"},
    )
    get = Mock(return_value=unrelated)
    monkeypatch.setattr(demo.httpx, "get", get)

    assert demo.service_name(str(request.url)) is None

    get.side_effect = httpx.ConnectError("unavailable", request=request)
    assert demo.service_name(str(request.url)) is None


def test_choose_ports_avoids_busy_defaults(monkeypatch):
    monkeypatch.setattr(
        demo,
        "port_is_free",
        lambda port: port in {8002, 8003},
    )

    assert demo.choose_ports() == (8002, 8003)


def test_choose_ports_preserves_free_dashboard_default(monkeypatch):
    monkeypatch.setattr(
        demo,
        "port_is_free",
        lambda port: port in {8001, 8002},
    )

    assert demo.choose_ports() == (8002, 8001)


def test_dashboard_readiness_requires_html_page(monkeypatch):
    request = httpx.Request("GET", "http://127.0.0.1:8001")
    html = httpx.Response(
        200,
        request=request,
        headers={"content-type": "text/html; charset=utf-8"},
    )
    get = Mock(return_value=html)
    monkeypatch.setattr(demo.httpx, "get", get)

    assert demo.dashboard_is_ready(str(request.url)) is True

    get.return_value = httpx.Response(
        404,
        request=request,
        headers={"content-type": "application/json"},
    )
    assert demo.dashboard_is_ready(str(request.url)) is False


def test_main_reuses_running_protocolsmith(monkeypatch, capsys):
    monkeypatch.setattr(
        demo,
        "existing_protocolsmith_is_ready",
        lambda *_: True,
    )
    opened: list[str] = []
    monkeypatch.setattr(demo, "open_dashboard", opened.append)

    demo.main()

    assert opened == ["http://127.0.0.1:8001"]
    output = capsys.readouterr().out
    assert "ProtocolSmith is already running" in output
    assert "Laboratory: http://127.0.0.1:8000" in output
    assert "Dashboard: http://127.0.0.1:8001" in output


def test_main_wires_alternate_ports_into_both_services(monkeypatch):
    monkeypatch.setattr(
        demo,
        "existing_protocolsmith_is_ready",
        lambda *_: False,
    )
    monkeypatch.setattr(demo, "choose_ports", lambda: (8002, 8001))
    lab_process = Mock()
    dashboard_process = Mock()
    lab_process.poll.return_value = None
    dashboard_process.poll.return_value = None
    popen = Mock(side_effect=[lab_process, dashboard_process])
    monkeypatch.setattr(demo.subprocess, "Popen", popen)
    monkeypatch.setattr(demo, "wait_until_ready", Mock())
    monkeypatch.setattr(demo, "open_dashboard", Mock())
    monkeypatch.setattr(demo, "stop_process", Mock())
    monkeypatch.setattr(
        demo.time,
        "sleep",
        Mock(side_effect=KeyboardInterrupt),
    )

    demo.main()

    lab_call, dashboard_call = popen.call_args_list
    assert lab_call.args[0][-1] == "8002"
    assert dashboard_call.args[0][-1] == "8001"
    assert lab_call.kwargs["env"]["PROTOCOLSMITH_LAB_URL"] == "http://127.0.0.1:8002"
    assert (
        dashboard_call.kwargs["env"]["PROTOCOLSMITH_BRIDGE_URL"]
        == "http://127.0.0.1:8001"
    )
    assert (
        dashboard_call.kwargs["env"]["PROTOCOLSMITH_MODERN_BASE_URL"]
        == "http://127.0.0.1:8002/v2"
    )


def test_open_dashboard_prints_manual_url_when_browser_fails(
    monkeypatch,
    capsys,
):
    monkeypatch.delenv("PROTOCOLSMITH_NO_BROWSER", raising=False)
    monkeypatch.setattr(demo, "try_open_dashboard", lambda *_args: False)

    demo.open_dashboard("http://127.0.0.1:8001")

    output = capsys.readouterr().out
    assert "did not open automatically" in output
    assert "http://127.0.0.1:8001" in output


def test_try_open_dashboard_suppresses_macos_launcher_output(monkeypatch):
    monkeypatch.setattr(demo.sys, "platform", "darwin")
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(demo.subprocess, "run", run)

    assert demo.try_open_dashboard("http://127.0.0.1:8001") is True

    run.assert_called_once_with(
        ["open", "http://127.0.0.1:8001"],
        check=False,
        stdout=demo.subprocess.DEVNULL,
        stderr=demo.subprocess.DEVNULL,
        timeout=5,
    )


def test_open_dashboard_honors_headless_mode(monkeypatch, capsys):
    monkeypatch.setenv("PROTOCOLSMITH_NO_BROWSER", "1")
    browser_open = Mock()
    monkeypatch.setattr(demo.webbrowser, "open", browser_open)

    demo.open_dashboard("http://127.0.0.1:8001")

    browser_open.assert_not_called()
    output = capsys.readouterr().out
    assert "opening is disabled" in output
    assert "http://127.0.0.1:8001" in output
