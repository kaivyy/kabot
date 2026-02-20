# tests/cron/test_parse.py
from kabot.cron.parse import parse_absolute_time_ms, parse_relative_time_ms

def test_iso_timestamp():
    result = parse_absolute_time_ms("2026-02-15T10:00:00+07:00")
    assert isinstance(result, int)
    assert result > 0

def test_relative_minutes():
    result = parse_relative_time_ms("5 menit")
    assert result == 5 * 60 * 1000

def test_relative_hours():
    result = parse_relative_time_ms("2 jam")
    assert result == 2 * 60 * 60 * 1000

def test_natural_language():
    result = parse_relative_time_ms("in 30 minutes")
    assert result == 30 * 60 * 1000

def test_multilingual_relative_time_support():
    assert parse_relative_time_ms("3 minit") == 3 * 60 * 1000
    assert parse_relative_time_ms("2 นาที") == 2 * 60 * 1000
    assert parse_relative_time_ms("4 分钟后") == 4 * 60 * 1000

def test_invalid_returns_none():
    assert parse_absolute_time_ms("not a date") is None
    assert parse_relative_time_ms("not a time") is None
