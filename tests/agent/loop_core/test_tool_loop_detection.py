"""Tests for tool loop detection."""

import pytest
from kabot.agent.loop_core.tool_loop_detection import (
    LoopDetector,
    LoopDetectionResult,
)


def test_no_loop_on_first_call():
    detector = LoopDetector()
    result = detector.check("exec", {"command": "ls"})
    assert result.stuck is False


def test_detects_generic_repeat():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for _ in range(5):
        detector.record("exec", {"command": "ls"})
    result = detector.check("exec", {"command": "ls"})
    assert result.stuck is True
    assert result.level == "critical"


def test_warns_before_critical():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for _ in range(3):
        detector.record("exec", {"command": "ls"})
    result = detector.check("exec", {"command": "ls"})
    assert result.stuck is True
    assert result.level == "warning"


def test_no_loop_for_different_params():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for i in range(10):
        detector.record("exec", {"command": f"cmd_{i}"})
    result = detector.check("exec", {"command": "cmd_new"})
    assert result.stuck is False


def test_detects_ping_pong():
    detector = LoopDetector(warning_threshold=3, critical_threshold=5)
    for _ in range(3):
        detector.record("read_file", {"path": "a.py"})
        detector.record("write_file", {"path": "a.py", "content": "x"})
    result = detector.check("read_file", {"path": "a.py"})
    assert result.stuck is True


def test_sliding_window():
    detector = LoopDetector(history_size=5)
    for i in range(10):
        detector.record("exec", {"command": f"different_{i}"})
    # Old entries should be evicted
    assert len(detector._history) <= 5
