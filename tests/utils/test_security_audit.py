"""Tests for Security Auditor."""
import pytest
from pathlib import Path
from kabot.utils.security_audit import SecurityAuditor

def test_scan_secrets(tmp_path):
    """Test that secrets are correctly identified."""
    # Create dummy workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    # Create file with secret
    secret_file = workspace / "secrets.txt"
    secret_file.write_text("My key is sk-123456789012345678901234567890123456789012345678")
    
    # Create file with another secret
    other_file = workspace / "other.py"
    other_file.write_text("api_key = 'AIzaSyA12345678901234567890123456789012'")
    
    auditor = SecurityAuditor(workspace)
    findings = auditor.scan_secrets()
    
    assert len(findings) == 3
    items = [f["item"] for f in findings]
    assert "OpenAI API Key" in items
    assert "Google API Key" in items
    assert "Generic Secret" in items

def test_scan_secrets_ignore_dirs(tmp_path):
    """Test that ignored directories are skipped."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    git_dir = workspace / ".git"
    git_dir.mkdir()
    secret_file = git_dir / "secret.txt"
    secret_file.write_text("sk-123456789012345678901234567890123456789012345678")
    
    auditor = SecurityAuditor(workspace)
    findings = auditor.scan_secrets()
    
    assert len(findings) == 0
