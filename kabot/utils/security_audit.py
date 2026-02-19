"""Security audit utilities."""

import os
import re
from pathlib import Path
from typing import List, Dict, Any

from kabot.utils.windows_acl import WindowsACL

# Common secret patterns (enhanced for Phase 13)
SECRET_PATTERNS = {
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{48}",
    "Anthropic API Key": r"sk-ant-at03-[a-zA-Z0-9\-_]{93}AA",
    "Google API Key": r"AIza[a-zA-Z0-9\-_]{35}",
    "GitHub Token": r"gh[pousr]_[A-Za-z0-9_]{36,255}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"(?i)aws_secret_access_key\s*[:=]\s*['\"]([A-Za-z0-9/+=]{40})['\"]",
    "Slack Token": r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}",
    "Stripe API Key": r"sk_live_[0-9a-zA-Z]{24,}",
    "Private Key": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "Generic Secret": r"(?i)(api_key|secret|password|token)\s*[:=]\s*['\"]([a-zA-Z0-9\-_]{16,})['\"]"
}

class SecurityAuditor:
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def run_audit(self) -> List[Dict[str, Any]]:
        """Run all security checks."""
        findings = []
        findings.extend(self.scan_secrets())
        findings.extend(self.scan_environment_secrets())
        findings.extend(self.check_permissions())
        return findings

    def run_config_audit(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run security checks on configuration."""
        findings = []
        findings.extend(self.check_network_security(config))
        findings.extend(self.check_redaction_policy(config))
        return findings

    def scan_secrets(self) -> List[Dict[str, Any]]:
        """Scan workspace for exposed secrets."""
        findings = []
        
        # Files to ignore
        ignore_dirs = {".git", "__pycache__", ".pytest_cache", ".worktrees", "venv", ".venv"}
        
        for root, dirs, files in os.walk(self.workspace_path):
            # Prune ignore dirs
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # Skip binary files
                if file_path.suffix.lower() in {".png", ".jpg", ".pyc", ".db", ".exe"}:
                    continue
                    
                try:
                    content = file_path.read_text(errors="ignore")
                    for name, pattern in SECRET_PATTERNS.items():
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            findings.append({
                                "type": "Secret Exposure",
                                "severity": "CRITICAL",
                                "item": name,
                                "file": str(file_path.relative_to(self.workspace_path)),
                                "detail": f"Potential {name} found"
                            })
                except Exception:
                    continue

        return findings

    def scan_environment_secrets(self) -> List[Dict[str, Any]]:
        """Scan environment variables for exposed secrets."""
        findings = []

        for key, value in os.environ.items():
            # Skip empty values
            if not value:
                continue

            # Check for secret patterns in environment variable values
            for name, pattern in SECRET_PATTERNS.items():
                if re.search(pattern, value):
                    findings.append({
                        "type": "Secret Exposure",
                        "severity": "CRITICAL",
                        "item": f"{name} in Environment Variable",
                        "file": f"Environment: {key}",
                        "detail": f"Potential {name} found in environment variable '{key}'"
                    })
                    break  # Only report once per env var

        return findings

    def check_network_security(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if services bind to public interfaces without auth."""
        findings = []
        public_hosts = ["0.0.0.0", "::", "*"]

        # Legacy API schema check (backward compatibility)
        api_config = config.get("api", {})
        api_host = api_config.get("host", "127.0.0.1")
        auth_enabled = api_config.get("auth_enabled", False)

        if api_host in public_hosts:
            if not auth_enabled:
                findings.append({
                    "type": "Network Security",
                    "severity": "HIGH",
                    "item": "Public API Without Authentication",
                    "file": "config",
                    "detail": f"API server binds to {api_host} without authentication enabled",
                    "remediation": "Set api.host to '127.0.0.1' or enable api.auth_enabled"
                })

        # Legacy WebSocket schema check (backward compatibility)
        ws_config = config.get("websocket", {})
        ws_host = ws_config.get("host", "127.0.0.1")
        ws_auth = ws_config.get("auth_enabled", False)

        if ws_host in public_hosts:
            if not ws_auth:
                findings.append({
                    "type": "Network Security",
                    "severity": "HIGH",
                    "item": "Public WebSocket Without Authentication",
                    "file": "config",
                    "detail": f"WebSocket server binds to {ws_host} without authentication",
                    "remediation": "Set websocket.host to '127.0.0.1' or enable websocket.auth_enabled"
                })

        # Current gateway schema check
        gateway_config = config.get("gateway", {})
        gateway_host = gateway_config.get("host", "127.0.0.1")
        gateway_token = (gateway_config.get("auth_token") or "").strip()

        if gateway_host in public_hosts and not gateway_token:
            findings.append({
                "type": "Network Security",
                "severity": "HIGH",
                "item": "Public Gateway Without Authentication",
                "file": "config",
                "detail": f"Gateway binds to {gateway_host} without auth token configured",
                "remediation": "Set gateway.host to '127.0.0.1' or configure gateway.auth_token"
            })

        return findings

    def check_redaction_policy(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if sensitive data redaction is enabled."""
        findings = []

        # Check logging redaction
        logging_config = config.get("logging", {})
        redact_sensitive = logging_config.get("redact_sensitive", True)

        if redact_sensitive is False:
            findings.append({
                "type": "Privacy Policy",
                "severity": "MEDIUM",
                "item": "Sensitive Data Redaction Disabled",
                "file": "config",
                "detail": "Sensitive data redaction is disabled in logging configuration",
                "remediation": "Set logging.redact_sensitive to true"
            })

        # Check if PII logging is enabled
        log_pii = logging_config.get("log_pii", False)
        if log_pii is True:
            findings.append({
                "type": "Privacy Policy",
                "severity": "HIGH",
                "item": "PII Logging Enabled",
                "file": "config",
                "detail": "Personally Identifiable Information (PII) logging is enabled",
                "remediation": "Set logging.log_pii to false"
            })

        # Check telemetry settings
        telemetry_config = config.get("telemetry", {})
        send_user_data = telemetry_config.get("send_user_data", False)

        if send_user_data is True:
            findings.append({
                "type": "Privacy Policy",
                "severity": "MEDIUM",
                "item": "User Data Telemetry Enabled",
                "file": "config",
                "detail": "User data is being sent to telemetry services",
                "remediation": "Set telemetry.send_user_data to false"
            })

        return findings

    def check_permissions(self) -> List[Dict[str, Any]]:
        """Check for insecure file permissions."""
        findings = []

        if os.name == "nt":
            # Windows: Use ACL checks
            findings.extend(self._check_windows_permissions())
        else:
            # Unix: Use traditional permission bits
            findings.extend(self._check_unix_permissions())

        return findings

    def _check_windows_permissions(self) -> List[Dict[str, Any]]:
        """Check Windows ACL permissions."""
        findings = []

        # Check important directories
        important_dirs = [
            self.workspace_path / ".kabot",
            self.workspace_path / "config",
            self.workspace_path / "data",
            self.workspace_path / "credentials"
        ]

        for dir_path in important_dirs:
            if dir_path.exists():
                findings.extend(WindowsACL.check_directory_permissions(dir_path))

        # Check sensitive files
        for root, dirs, files in os.walk(self.workspace_path):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".pytest_cache", ".worktrees", "venv", ".venv"}]

            for file in files:
                file_path = Path(root) / file
                # Only check sensitive files to avoid performance issues
                if WindowsACL._is_sensitive_file(file_path):
                    findings.extend(WindowsACL.check_file_permissions(file_path))

        return findings

    def _check_unix_permissions(self) -> List[Dict[str, Any]]:
        """Check Unix permission bits."""
        findings = []

        for root, dirs, files in os.walk(self.workspace_path):
            for item in dirs + files:
                path = Path(root) / item
                try:
                    mode = os.stat(path).st_mode
                    # Check if world-writable (0o002)
                    if mode & 0o002:
                        findings.append({
                            "type": "Insecure Permission",
                            "severity": "HIGH",
                            "item": "World Writable",
                            "file": str(path.relative_to(self.workspace_path)),
                            "detail": f"File is world-writable (mode: {oct(mode & 0o777)})"
                        })
                except Exception:
                    continue

        return findings
