from types import SimpleNamespace

from kabot.cli import commands


def _mk_config(*, port=18790, bind_mode="local", tailscale=False):
    return SimpleNamespace(
        gateway=SimpleNamespace(
            port=port,
            bind_mode=bind_mode,
            tailscale=tailscale,
        )
    )


def test_resolve_gateway_runtime_port_uses_config_when_cli_absent():
    cfg = _mk_config(port=19999)
    assert commands._resolve_gateway_runtime_port(cfg, None) == 19999


def test_resolve_gateway_runtime_port_prefers_cli_override():
    cfg = _mk_config(port=19999)
    assert commands._resolve_gateway_runtime_port(cfg, 18888) == 18888


def test_resolve_gateway_runtime_port_falls_back_when_config_invalid():
    cfg = _mk_config(port=0)
    assert commands._resolve_gateway_runtime_port(cfg, None) == 18790


def test_resolve_tailscale_mode_serve_when_bind_mode_tailscale():
    cfg = _mk_config(bind_mode="tailscale", tailscale=False)
    assert commands._resolve_tailscale_mode(cfg) == "serve"


def test_resolve_tailscale_mode_funnel_when_toggle_enabled():
    cfg = _mk_config(bind_mode="local", tailscale=True)
    assert commands._resolve_tailscale_mode(cfg) == "funnel"


def test_configure_tailscale_runtime_runs_serve(monkeypatch):
    calls = []

    def _fake_runner(args, timeout_s=10):
        calls.append(args)
        if args[:2] == ["status", "--json"]:
            return (
                0,
                '{"BackendState":"Running","Self":{"DNSName":"kabot.tailnet.ts.net.","TailscaleIPs":["100.90.1.2"]}}',
                "",
            )
        return (0, "ok", "")

    result = commands._configure_tailscale_runtime("serve", 18790, runner=_fake_runner)

    assert result["ok"] is True
    assert result["mode"] == "serve"
    assert result["https_url"] == "https://kabot.tailnet.ts.net/"
    assert calls[0] == ["status", "--json"]
    assert calls[1] == ["serve", "--bg", "--yes", "18790"]


def test_configure_tailscale_runtime_stops_when_status_fails():
    def _fake_runner(args, timeout_s=10):
        assert args == ["status", "--json"]
        return (1, "", "tailscaled not running")

    result = commands._configure_tailscale_runtime("funnel", 18790, runner=_fake_runner)

    assert result["ok"] is False
    assert "tailscaled not running" in result["error"]
