"""Quarantined Windows service-status test.

Reason: behavior changed and is environment/platform dependent in current runtime.
"""

from unittest.mock import patch

from kabot.core.daemon import get_service_status


def test_get_service_status_windows():
    """Legacy expectation for Windows service status."""
    with patch("sys.platform", "win32"):
        status = get_service_status()
        assert status["platform"] == "win32"
        assert status["service_available"] is False
        assert status["service_type"] == "task_scheduler"
        assert "coming soon" in status["note"]
