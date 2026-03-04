import socket

import pytest
import typer

from kabot.cli.commands import _is_port_in_use_error, _preflight_gateway_port


def test_is_port_in_use_error_detects_windows_bind_conflict():
    exc = OSError(10048, "only one usage of each socket address is normally permitted")
    assert _is_port_in_use_error(exc) is True


def test_is_port_in_use_error_detects_posix_bind_conflict():
    exc = OSError(98, "address already in use")
    assert _is_port_in_use_error(exc) is True


def test_is_port_in_use_error_ignores_other_os_errors():
    exc = OSError(2, "no such file or directory")
    assert _is_port_in_use_error(exc) is False


def test_preflight_gateway_port_allows_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    # Should not raise when the port is free.
    _preflight_gateway_port("127.0.0.1", free_port)


def test_preflight_gateway_port_raises_exit_when_port_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        busy_port = listener.getsockname()[1]

        with pytest.raises(typer.Exit) as exc_info:
            _preflight_gateway_port("127.0.0.1", busy_port)

        assert exc_info.value.exit_code == 78
