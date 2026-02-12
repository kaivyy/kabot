"""Security audit utilities."""

import os
import re
from pathlib import Path
from typing import List, Dict, Any

# Common secret patterns
SECRET_PATTERNS = {
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{48}",
    "Anthropic API Key": r"sk-ant-at03-[a-zA-Z0-9\-_]{93}AA",
    "Google API Key": r"AIza[a-zA-Z0-9\-_]{35}",
    "Generic Secret": r"(?i)(api_key|secret|password|token)\s*[:=]\s*['\"]([a-zA-Z0-9\-_]{16,})['\"]"
}

class SecurityAuditor:
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def run_audit(self) -> List[Dict[str, Any]]:
        """Run all security checks."""
        findings = []
        findings.extend(self.scan_secrets())
        findings.extend(self.check_permissions())
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

    def check_permissions(self) -> List[Dict[str, Any]]:
        """Check for insecure file permissions."""
        findings = []
        
        # Note: on Windows, permission bits work differently
        if os.name == "nt":
            return findings
            
        # For Unix-like systems
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
