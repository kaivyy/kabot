"""Tests for Security Auditor."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch
from kabot.utils.security_audit import SecurityAuditor


class TestSecretScanning:
    """Test secret scanning functionality."""

    def test_scan_secrets_openai(self, tmp_path):
        """Test OpenAI API key detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        secret_file = workspace / "secrets.txt"
        secret_file.write_text("My key is sk-123456789012345678901234567890123456789012345678")

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        assert len(findings) >= 1
        assert any(f["item"] == "OpenAI API Key" for f in findings)

    def test_scan_secrets_multiple_patterns(self, tmp_path):
        """Test that multiple secret types are detected."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        secret_file = workspace / "secrets.txt"
        secret_file.write_text("My key is sk-123456789012345678901234567890123456789012345678")

        other_file = workspace / "other.py"
        other_file.write_text("api_key = 'AIzaSyA12345678901234567890123456789012'")

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        assert len(findings) == 3
        items = [f["item"] for f in findings]
        assert "OpenAI API Key" in items
        assert "Google API Key" in items
        assert "Generic Secret" in items

    def test_scan_secrets_github_token(self, tmp_path):
        """Test GitHub token detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        secret_file = workspace / "config.py"
        secret_file.write_text("GITHUB_TOKEN = 'ghp_1234567890123456789012345678901234567890'")

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        assert any(f["item"] == "GitHub Token" for f in findings)

    def test_scan_secrets_aws_keys(self, tmp_path):
        """Test AWS key detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        secret_file = workspace / "aws.conf"
        secret_file.write_text("""
        aws_access_key_id = AKIAIOSFODNN7EXAMPLE
        aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        """)

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        assert any(f["item"] == "AWS Access Key" for f in findings)
        assert any(f["item"] == "AWS Secret Key" for f in findings)

    def test_scan_secrets_private_key(self, tmp_path):
        """Test private key detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        key_file = workspace / "id_rsa"
        key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...")

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        assert any(f["item"] == "Private Key" for f in findings)

    def test_scan_secrets_ignore_dirs(self, tmp_path):
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

    def test_scan_secrets_ignore_binary_files(self, tmp_path):
        """Test that binary files are skipped."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        binary_file = workspace / "image.png"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"sk-123456789012345678901234567890123456789012345678")

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        assert len(findings) == 0


class TestEnvironmentSecretScanning:
    """Test environment variable secret scanning."""

    def test_scan_environment_secrets_found(self, tmp_path):
        """Test that secrets in environment variables are detected."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch.dict(os.environ, {"MY_API_KEY": "sk-123456789012345678901234567890123456789012345678"}):
            auditor = SecurityAuditor(workspace)
            findings = auditor.scan_environment_secrets()

            assert len(findings) >= 1
            assert any("Environment Variable" in f["item"] for f in findings)
            assert any("MY_API_KEY" in f["file"] for f in findings)

    def test_scan_environment_secrets_empty_values(self, tmp_path):
        """Test that empty environment variables are skipped."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            auditor = SecurityAuditor(workspace)
            findings = auditor.scan_environment_secrets()

            # Should not report empty values
            assert not any("EMPTY_VAR" in f["file"] for f in findings)

    def test_scan_environment_secrets_no_secrets(self, tmp_path):
        """Test that safe environment variables are not flagged."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/home/user"}):
            auditor = SecurityAuditor(workspace)
            findings = auditor.scan_environment_secrets()

            # Should not report PATH or HOME
            assert not any("PATH" in f["file"] for f in findings)
            assert not any("HOME" in f["file"] for f in findings)


class TestNetworkSecurity:
    """Test network security checks."""

    def test_check_network_security_public_api_no_auth(self, tmp_path):
        """Test detection of public API without authentication."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "api": {
                "host": "0.0.0.0",
                "auth_enabled": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(config)

        assert len(findings) >= 1
        assert any(f["item"] == "Public API Without Authentication" for f in findings)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_check_network_security_public_api_with_auth(self, tmp_path):
        """Test that public API with auth is allowed."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "api": {
                "host": "0.0.0.0",
                "auth_enabled": True
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(config)

        # Should not report if auth is enabled
        assert not any(f["item"] == "Public API Without Authentication" for f in findings)

    def test_check_network_security_localhost_no_auth(self, tmp_path):
        """Test that localhost binding without auth is allowed."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "api": {
                "host": "127.0.0.1",
                "auth_enabled": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(config)

        # Should not report localhost binding
        assert not any(f["item"] == "Public API Without Authentication" for f in findings)

    def test_check_network_security_websocket(self, tmp_path):
        """Test WebSocket security checks."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "websocket": {
                "host": "0.0.0.0",
                "auth_enabled": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(config)

        assert any(f["item"] == "Public WebSocket Without Authentication" for f in findings)

    def test_check_network_security_ipv6_wildcard(self, tmp_path):
        """Test IPv6 wildcard detection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "api": {
                "host": "::",
                "auth_enabled": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_network_security(config)

        assert any(f["item"] == "Public API Without Authentication" for f in findings)


class TestRedactionPolicy:
    """Test redaction policy checks."""

    def test_check_redaction_policy_disabled(self, tmp_path):
        """Test detection of disabled redaction."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "logging": {
                "redact_sensitive": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_redaction_policy(config)

        assert len(findings) >= 1
        assert any(f["item"] == "Sensitive Data Redaction Disabled" for f in findings)
        assert any(f["severity"] == "MEDIUM" for f in findings)

    def test_check_redaction_policy_enabled(self, tmp_path):
        """Test that enabled redaction is not flagged."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "logging": {
                "redact_sensitive": True
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_redaction_policy(config)

        # Should not report if redaction is enabled
        assert not any(f["item"] == "Sensitive Data Redaction Disabled" for f in findings)

    def test_check_redaction_policy_pii_logging(self, tmp_path):
        """Test detection of PII logging."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "logging": {
                "log_pii": True
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_redaction_policy(config)

        assert any(f["item"] == "PII Logging Enabled" for f in findings)
        assert any(f["severity"] == "HIGH" for f in findings)

    def test_check_redaction_policy_telemetry(self, tmp_path):
        """Test detection of user data telemetry."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "telemetry": {
                "send_user_data": True
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_redaction_policy(config)

        assert any(f["item"] == "User Data Telemetry Enabled" for f in findings)
        assert any(f["severity"] == "MEDIUM" for f in findings)

    def test_check_redaction_policy_default_safe(self, tmp_path):
        """Test that default config is safe."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "logging": {
                "redact_sensitive": True,
                "log_pii": False
            },
            "telemetry": {
                "send_user_data": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.check_redaction_policy(config)

        # Should not report any issues with safe defaults
        assert len(findings) == 0


class TestIntegration:
    """Integration tests for security auditor."""

    def test_run_audit_comprehensive(self, tmp_path):
        """Test full audit run."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create file with secret
        secret_file = workspace / "config.py"
        secret_file.write_text("API_KEY = 'sk-123456789012345678901234567890123456789012345678'")

        auditor = SecurityAuditor(workspace)
        findings = auditor.run_audit()

        # Should find at least the secret
        assert len(findings) >= 1
        assert any(f["type"] == "Secret Exposure" for f in findings)

    def test_run_config_audit_comprehensive(self, tmp_path):
        """Test full config audit run."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        config = {
            "api": {
                "host": "0.0.0.0",
                "auth_enabled": False
            },
            "logging": {
                "redact_sensitive": False
            }
        }

        auditor = SecurityAuditor(workspace)
        findings = auditor.run_config_audit(config)

        # Should find both network and redaction issues
        assert len(findings) >= 2
        assert any(f["type"] == "Network Security" for f in findings)
        assert any(f["type"] == "Privacy Policy" for f in findings)

    def test_finding_structure(self, tmp_path):
        """Test that findings have correct structure."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        secret_file = workspace / "test.txt"
        secret_file.write_text("sk-123456789012345678901234567890123456789012345678")

        auditor = SecurityAuditor(workspace)
        findings = auditor.scan_secrets()

        # Check finding structure
        for finding in findings:
            assert "type" in finding
            assert "severity" in finding
            assert "item" in finding
            assert "file" in finding
            assert "detail" in finding

