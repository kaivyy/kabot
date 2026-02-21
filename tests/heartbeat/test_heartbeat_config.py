"""Tests for HeartbeatDefaults and active-hours filtering."""

from kabot.config.schema import HeartbeatDefaults


class TestHeartbeatDefaults:
    def test_defaults(self):
        cfg = HeartbeatDefaults()
        assert cfg.enabled is True
        assert cfg.interval_minutes == 30
        assert cfg.target_channel == "last"
        assert cfg.target_to == ""
        assert cfg.active_hours_start == ""
        assert cfg.active_hours_end == ""

    def test_custom(self):
        cfg = HeartbeatDefaults(
            interval_minutes=15,
            target_channel="telegram",
            target_to="123456",
            active_hours_start="08:00",
            active_hours_end="22:00",
        )
        assert cfg.interval_minutes == 15
        assert cfg.target_channel == "telegram"


class TestHeartbeatActiveHours:
    def test_is_within_active_hours_no_config(self):
        from kabot.heartbeat.service import is_within_active_hours

        assert is_within_active_hours("", "") is True

    def test_is_within_active_hours_inside(self):
        from kabot.heartbeat.service import is_within_active_hours

        result = is_within_active_hours("00:00", "23:59", test_hour=12)
        assert result is True

    def test_is_within_active_hours_outside(self):
        from kabot.heartbeat.service import is_within_active_hours

        result = is_within_active_hours("09:00", "17:00", test_hour=3)
        assert result is False
