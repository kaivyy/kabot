"""
Windows ACL (Access Control List) security checker.

Pattern from OpenClaw: security/windows-acl.ts
Uses icacls to check file/directory permissions on Windows.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class WindowsACL:
    """
    Windows ACL checker using icacls command.

    Detects insecure file permissions that could lead to security vulnerabilities.
    """

    @staticmethod
    def check_directory_permissions(path: Path) -> List[Dict[str, Any]]:
        """
        Check if directory has secure permissions.

        Args:
            path: Directory path to check

        Returns:
            List of security findings
        """
        if os.name != 'nt':
            return []

        findings = []

        try:
            # Check if path exists
            if not path.exists():
                return findings

            # Check if world-writable
            if WindowsACL.is_world_writable(path):
                findings.append({
                    'type': 'Insecure Permission',
                    'severity': 'HIGH',
                    'item': 'World Writable Directory',
                    'file': str(path),
                    'detail': 'Directory is writable by Everyone or Users group',
                    'remediation': f'Run: icacls "{path}" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F"'
                })

            # Check if running as Administrator unnecessarily
            if WindowsACL.is_running_as_admin():
                findings.append({
                    'type': 'Privilege Escalation Risk',
                    'severity': 'MEDIUM',
                    'item': 'Running as Administrator',
                    'file': str(path),
                    'detail': 'Process is running with Administrator privileges',
                    'remediation': 'Run kabot as a regular user unless elevated access is required'
                })

        except Exception as e:
            logger.warning(f"Error checking Windows ACL for {path}: {e}")

        return findings

    @staticmethod
    def is_world_writable(path: Path) -> bool:
        """
        Check if path is writable by Everyone or Users group.

        Args:
            path: Path to check

        Returns:
            True if world-writable
        """
        if os.name != 'nt':
            return False

        try:
            acl_info = WindowsACL.get_acl_info(path)
            if not acl_info:
                return False

            # Check for dangerous permissions
            dangerous_groups = ['Everyone', 'BUILTIN\\Users', 'Users']

            for entry in acl_info.get('entries', []):
                principal = entry.get('principal', '')
                permissions = entry.get('permissions', [])

                # Check if dangerous group has write permissions
                if any(group.lower() in principal.lower() for group in dangerous_groups):
                    if any(perm in permissions for perm in ['F', 'M', 'W', 'WD']):
                        return True

            return False

        except Exception as e:
            logger.warning(f"Error checking if world-writable: {e}")
            return False

    @staticmethod
    def get_acl_info(path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse icacls output into structured data.

        Args:
            path: Path to get ACL info for

        Returns:
            Dict with ACL information or None if failed
        """
        if os.name != 'nt':
            return None

        try:
            # Run icacls command
            result = subprocess.run(
                ['icacls', str(path)],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode != 0:
                return None

            # Parse output
            output = result.stdout.strip()
            lines = output.split('\n')

            if len(lines) < 2:
                return None

            # First line is the path
            # Subsequent lines are ACL entries
            entries = []

            for line in lines[1:]:
                line = line.strip()
                if not line or line.startswith('Successfully'):
                    continue

                # Parse ACL entry format: "DOMAIN\User:(permissions)"
                match = re.match(r'^(.+?):\(([^)]+)\)(.*)$', line)
                if match:
                    principal = match.group(1).strip()
                    permissions_str = match.group(2).strip()
                    inheritance = match.group(3).strip() if match.group(3) else ''

                    # Parse permission flags
                    # F = Full control, M = Modify, RX = Read & Execute, R = Read, W = Write
                    # OI = Object Inherit, CI = Container Inherit, IO = Inherit Only
                    permissions = [p.strip() for p in permissions_str.split(',') if p.strip()]

                    entries.append({
                        'principal': principal,
                        'permissions': permissions,
                        'inheritance': inheritance
                    })

            return {
                'path': str(path),
                'entries': entries
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"icacls command timed out for {path}")
            return None
        except Exception as e:
            logger.warning(f"Error getting ACL info: {e}")
            return None

    @staticmethod
    def is_running_as_admin() -> bool:
        """
        Check if current process is running as Administrator.

        Returns:
            True if running as admin
        """
        if os.name != 'nt':
            return False

        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def check_file_permissions(path: Path) -> List[Dict[str, Any]]:
        """
        Check if file has secure permissions.

        Args:
            path: File path to check

        Returns:
            List of security findings
        """
        if os.name != 'nt':
            return []

        findings = []

        try:
            if not path.exists() or not path.is_file():
                return findings

            # Check if world-readable for sensitive files
            if WindowsACL._is_sensitive_file(path):
                if WindowsACL.is_world_readable(path):
                    findings.append({
                        'type': 'Insecure Permission',
                        'severity': 'HIGH',
                        'item': 'Sensitive File World Readable',
                        'file': str(path),
                        'detail': 'Sensitive file is readable by Everyone or Users group',
                        'remediation': f'Run: icacls "{path}" /inheritance:r /grant:r "%USERNAME%:F"'
                    })

            # Check if world-writable
            if WindowsACL.is_world_writable(path):
                findings.append({
                    'type': 'Insecure Permission',
                    'severity': 'CRITICAL',
                    'item': 'File World Writable',
                    'file': str(path),
                    'detail': 'File is writable by Everyone or Users group',
                    'remediation': f'Run: icacls "{path}" /inheritance:r /grant:r "%USERNAME%:F"'
                })

        except Exception as e:
            logger.warning(f"Error checking file permissions for {path}: {e}")

        return findings

    @staticmethod
    def is_world_readable(path: Path) -> bool:
        """
        Check if path is readable by Everyone or Users group.

        Args:
            path: Path to check

        Returns:
            True if world-readable
        """
        if os.name != 'nt':
            return False

        try:
            acl_info = WindowsACL.get_acl_info(path)
            if not acl_info:
                return False

            dangerous_groups = ['Everyone', 'BUILTIN\\Users', 'Users']

            for entry in acl_info.get('entries', []):
                principal = entry.get('principal', '')
                permissions = entry.get('permissions', [])

                if any(group.lower() in principal.lower() for group in dangerous_groups):
                    if any(perm in permissions for perm in ['F', 'M', 'RX', 'R']):
                        return True

            return False

        except Exception:
            return False

    @staticmethod
    def _is_sensitive_file(path: Path) -> bool:
        """
        Check if file contains sensitive data.

        Args:
            path: File path to check

        Returns:
            True if file is sensitive
        """
        sensitive_patterns = [
            'config.json',
            'credentials',
            '.env',
            'secret',
            'token',
            'key',
            'password',
            '.db',
            '.sqlite'
        ]

        path_str = str(path).lower()
        return any(pattern in path_str for pattern in sensitive_patterns)
