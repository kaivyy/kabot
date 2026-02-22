"""Tests for structured security audit trail."""

import json
from pathlib import Path

import pytest

from kabot.security.audit_trail import AuditTrail


@pytest.fixture
def audit(tmp_path: Path) -> AuditTrail:
    return AuditTrail(log_dir=tmp_path / "audit")


class TestAuditTrail:
    def test_log_creates_jsonl_file(self, audit: AuditTrail, tmp_path: Path):
        audit.log(event="command.exec", data={"cmd": "ls"})
        files = list((tmp_path / "audit").glob("*.jsonl"))
        assert len(files) == 1

    def test_log_entry_has_required_fields(self, audit: AuditTrail, tmp_path: Path):
        audit.log(event="tool.invoke", data={"tool": "shell"}, actor="agent:main")
        log_file = list((tmp_path / "audit").glob("*.jsonl"))[0]
        line = log_file.read_text(encoding="utf-8").strip().split("\n")[0]
        entry = json.loads(line)
        assert entry["event"] == "tool.invoke"
        assert entry["actor"] == "agent:main"
        assert "timestamp" in entry
        assert "data" in entry

    def test_multiple_entries_append(self, audit: AuditTrail, tmp_path: Path):
        audit.log(event="a", data={})
        audit.log(event="b", data={})
        log_file = list((tmp_path / "audit").glob("*.jsonl"))[0]
        lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line]
        assert len(lines) == 2

    def test_query_by_event_type(self, audit: AuditTrail):
        audit.log(event="auth.login", data={"user": "admin"})
        audit.log(event="command.exec", data={"cmd": "rm -rf /"})
        audit.log(event="auth.login", data={"user": "bob"})
        results = audit.query(event="auth.login")
        assert len(results) == 2
