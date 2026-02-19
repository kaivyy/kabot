"""Focused tests for gateway-aware security audit checks."""

import shutil
import uuid
from pathlib import Path

from kabot.utils.security_audit import SecurityAuditor


def _make_workspace() -> Path:
    root = Path.cwd() / ".tmp-test-security-audit"
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / f"case-{uuid.uuid4().hex[:8]}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def test_gateway_public_without_token_is_flagged():
    workspace = _make_workspace()
    try:
        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(
            {
                "gateway": {
                    "host": "0.0.0.0",
                    "auth_token": "",
                }
            }
        )
        assert any(f["item"] == "Public Gateway Without Authentication" for f in findings)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_gateway_public_with_token_is_not_flagged():
    workspace = _make_workspace()
    try:
        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(
            {
                "gateway": {
                    "host": "0.0.0.0",
                    "auth_token": "kabot-test-token",
                }
            }
        )
        assert not any(f["item"] == "Public Gateway Without Authentication" for f in findings)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
