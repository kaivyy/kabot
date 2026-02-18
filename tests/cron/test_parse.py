# tests/cron/test_parse.py
from kabot.cron.parse import parse_absolute_time_ms, parse_relative_time_ms, parse_reminder_request

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

def test_invalid_returns_none():
    assert parse_absolute_time_ms("not a date") is None
    assert parse_relative_time_ms("not a time") is None


def test_reminder_indonesian_with_message():
    result = parse_reminder_request("ingatkan saya 2 menit lagi beli susu")
    assert result == {"offset_ms": 120000, "message": "beli susu"}


def test_reminder_indonesian_default_message():
    result = parse_reminder_request("ingatkan 2 menit lagi")
    assert result == {"offset_ms": 120000, "message": "Pengingat"}


def test_reminder_english_with_message():
    result = parse_reminder_request("remind me in 5 minutes to call mom")
    assert result == {"offset_ms": 300000, "message": "call mom"}


def test_reminder_non_relative_returns_none():
    assert parse_reminder_request("ingatkan saya besok") is None
