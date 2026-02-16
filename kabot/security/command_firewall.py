"""
Granular command execution firewall.

Pattern from OpenClaw: infra/exec-approvals.ts
Provides allowlist/deny/ask policies with tamper-proof configuration.
"""

import hashlib
import json
import re
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import yaml
from loguru import logger


class ApprovalDecision(Enum):
    """Command approval decision."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class CommandPattern:
    """Command pattern with description."""
    pattern: str
    description: str
    compiled_regex: Optional[re.Pattern] = None

    def __post_init__(self):
        """Compile regex pattern."""
        # Escape special regex characters except *
        regex_pattern = re.escape(self.pattern)
        # Convert escaped \* back to .* for wildcard matching
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        regex_pattern = f'^{regex_pattern}$'
        try:
            self.compiled_regex = re.compile(regex_pattern)
        except re.error as e:
            logger.error(f"Invalid pattern '{self.pattern}': {e}")
            self.compiled_regex = None

    def matches(self, command: str) -> bool:
        """Check if command matches this pattern."""
        if not self.compiled_regex:
            return False
        return bool(self.compiled_regex.match(command))


class CommandFirewall:
    """
    Granular command execution firewall.

    Provides three policy modes:
    - deny: Block all commands (safest)
    - ask: Prompt user for every command (default)
    - allowlist: Auto-approve commands matching allowlist patterns

    Features:
    - Pattern-based allowlist/denylist
    - Tamper-proof configuration with hash verification
    - Audit trail of all command executions
    - Clear remediation messages for denied commands
    """

    def __init__(self, config_path: Path):
        """
        Initialize command firewall.

        Args:
            config_path: Path to command approvals config file
        """
        self.config_path = Path(config_path)
        self.hash_path = self.config_path.with_suffix('.hash')
        self.policy: Dict[str, Any] = {}
        self.allowlist: List[CommandPattern] = []
        self.denylist: List[CommandPattern] = []
        self.config_hash: str = ""

        # Load and verify configuration
        self._load_policy()
        self._verify_integrity()

    def check_command(self, command: str) -> ApprovalDecision:
        """
        Check if command should be allowed, denied, or requires user approval.

        Args:
            command: Command to check

        Returns:
            ApprovalDecision (ALLOW, DENY, or ASK)
        """
        # Verify config integrity before each check
        if not self._verify_integrity():
            logger.critical("Config integrity check failed - denying all commands")
            return ApprovalDecision.DENY

        # Check denylist first (highest priority)
        for pattern in self.denylist:
            if pattern.matches(command):
                logger.warning(
                    f"Command denied by denylist: {command} "
                    f"(matched: {pattern.pattern})"
                )
                return ApprovalDecision.DENY

        # Get policy mode
        policy_mode = self.policy.get('policy', 'ask')

        if policy_mode == 'deny':
            # Deny all commands
            return ApprovalDecision.DENY

        elif policy_mode == 'allowlist':
            # Check allowlist
            for pattern in self.allowlist:
                if pattern.matches(command):
                    logger.info(
                        f"Command allowed by allowlist: {command} "
                        f"(matched: {pattern.pattern})"
                    )
                    return ApprovalDecision.ALLOW

            # Not in allowlist - ask user
            return ApprovalDecision.ASK

        else:  # policy_mode == 'ask' (default)
            # Ask user for all commands
            return ApprovalDecision.ASK

    def _load_policy(self) -> None:
        """Load policy from config file."""
        try:
            if not self.config_path.exists():
                # Create default config
                self._create_default_config()

            with open(self.config_path) as f:
                self.policy = yaml.safe_load(f) or {}

            # Parse allowlist patterns
            self.allowlist = []
            for item in self.policy.get('allowlist', []):
                pattern = CommandPattern(
                    pattern=item['pattern'],
                    description=item.get('description', '')
                )
                self.allowlist.append(pattern)

            # Parse denylist patterns
            self.denylist = []
            for item in self.policy.get('denylist', []):
                pattern = CommandPattern(
                    pattern=item['pattern'],
                    description=item.get('description', '')
                )
                self.denylist.append(pattern)

            # Compute and store hash
            self.config_hash = self._compute_hash()
            self._save_hash()

            logger.info(
                f"Loaded command firewall policy: {self.policy.get('policy', 'ask')} "
                f"({len(self.allowlist)} allowed, {len(self.denylist)} denied)"
            )

        except Exception as e:
            logger.error(f"Error loading command firewall policy: {e}")
            # Fail-safe: deny all commands
            self.policy = {'policy': 'deny'}
            self.allowlist = []
            self.denylist = []

    def _create_default_config(self) -> None:
        """Create default configuration file."""
        default_config = {
            'policy': 'ask',
            'allowlist': [
                {
                    'pattern': 'git status',
                    'description': 'Safe read-only git command'
                },
                {
                    'pattern': 'git diff*',
                    'description': 'View git changes'
                },
                {
                    'pattern': 'git log*',
                    'description': 'View git history'
                },
                {
                    'pattern': 'ls*',
                    'description': 'List directory contents'
                },
                {
                    'pattern': 'pwd',
                    'description': 'Print working directory'
                },
                {
                    'pattern': 'echo*',
                    'description': 'Print text'
                }
            ],
            'denylist': [
                {
                    'pattern': 'rm -rf *',
                    'description': 'Dangerous recursive delete'
                },
                {
                    'pattern': 'dd if=*',
                    'description': 'Low-level disk operations'
                },
                {
                    'pattern': 'mkfs*',
                    'description': 'Format filesystem'
                },
                {
                    'pattern': 'fdisk*',
                    'description': 'Partition disk'
                },
                {
                    'pattern': ':(){ :|:& };:',
                    'description': 'Fork bomb'
                }
            ]
        }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Created default command firewall config at {self.config_path}")

    def _compute_hash(self) -> str:
        """
        Compute SHA256 hash of config file.

        Returns:
            Hex digest of config file hash
        """
        try:
            with open(self.config_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Error computing config hash: {e}")
            return ""

    def _save_hash(self) -> None:
        """Save config hash to separate file."""
        try:
            with open(self.hash_path, 'w') as f:
                f.write(self.config_hash)
        except Exception as e:
            logger.error(f"Error saving config hash: {e}")

    def _verify_integrity(self) -> bool:
        """
        Verify config file has not been tampered with.

        Returns:
            True if config is valid and untampered
        """
        try:
            # Compute current hash
            current_hash = self._compute_hash()

            # Check if hash file exists
            if not self.hash_path.exists():
                # First run - save hash
                self.config_hash = current_hash
                self._save_hash()
                return True

            # Load stored hash
            with open(self.hash_path) as f:
                stored_hash = f.read().strip()

            # Compare hashes
            if current_hash != stored_hash:
                logger.critical(
                    f"Config integrity check FAILED! "
                    f"Config file may have been tampered with. "
                    f"Expected: {stored_hash}, Got: {current_hash}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error verifying config integrity: {e}")
            return False

    def reload_config(self) -> None:
        """Reload configuration from disk."""
        self._load_policy()
        if not self._verify_integrity():
            logger.critical("Config reload failed integrity check")

    def get_policy_info(self) -> Dict[str, Any]:
        """
        Get current policy information.

        Returns:
            Dict with policy mode, allowlist, and denylist info
        """
        return {
            'policy': self.policy.get('policy', 'ask'),
            'allowlist_count': len(self.allowlist),
            'denylist_count': len(self.denylist),
            'config_path': str(self.config_path),
            'integrity_verified': self._verify_integrity()
        }

    def add_to_allowlist(self, pattern: str, description: str) -> bool:
        """
        Add pattern to allowlist.

        Args:
            pattern: Command pattern to allow
            description: Description of what this pattern allows

        Returns:
            True if added successfully
        """
        try:
            # Load current config
            with open(self.config_path) as f:
                config = yaml.safe_load(f) or {}

            # Add to allowlist
            if 'allowlist' not in config:
                config['allowlist'] = []

            config['allowlist'].append({
                'pattern': pattern,
                'description': description
            })

            # Save config
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            # Reload
            self._load_policy()

            logger.info(f"Added to allowlist: {pattern}")
            return True

        except Exception as e:
            logger.error(f"Error adding to allowlist: {e}")
            return False
