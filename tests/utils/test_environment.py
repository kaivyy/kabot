"""Tests for runtime environment detection."""

from kabot.utils.environment import detect_runtime_environment, recommended_gateway_mode


def test_detect_runtime_environment_termux():
    info = detect_runtime_environment(
        env={
            "PREFIX": "/data/data/com.termux/files/usr",
            "ANDROID_ROOT": "/system",
        },
        sys_platform="linux",
        platform_system="Linux",
        proc_version_text="Linux version 6.1.0",
        dockerenv_exists=False,
    )

    assert info.is_termux is True
    assert info.is_linux is True
    assert info.is_headless is True
    assert recommended_gateway_mode(info) == "remote"


def test_detect_runtime_environment_vps_from_ssh():
    info = detect_runtime_environment(
        env={"SSH_CLIENT": "1 2 3"},
        sys_platform="linux",
        platform_system="Linux",
        proc_version_text="Linux version 6.1.0",
        dockerenv_exists=False,
    )

    assert info.is_vps is True
    assert info.is_headless is True
    assert recommended_gateway_mode(info) == "remote"


def test_detect_runtime_environment_wsl():
    info = detect_runtime_environment(
        env={},
        sys_platform="linux",
        platform_system="Linux",
        proc_version_text="microsoft-standard-WSL2",
        dockerenv_exists=False,
    )

    assert info.is_wsl is True
    assert info.is_linux is True


def test_detect_runtime_environment_desktop_defaults_local_mode():
    info = detect_runtime_environment(
        env={"DISPLAY": ":0"},
        sys_platform="darwin",
        platform_system="Darwin",
        proc_version_text="Darwin Kernel Version",
        dockerenv_exists=False,
    )

    assert info.is_macos is True
    assert info.has_display is True
    assert info.is_headless is False
    assert recommended_gateway_mode(info) == "local"
