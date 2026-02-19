"""
Granular command execution firewall.

Pattern from OpenClaw: infra/exec-approvals.ts
Provides allowlist/deny/ask policies with tamper-proof configuration.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from fnmatch import fnmatch
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


@dataclass
class ScopedPolicy:
    """Scoped policy entry for context-aware approval decisions."""

    name: str
    scope: Dict[str, str]
    policy: str
    allowlist: List[CommandPattern]
    denylist: List[CommandPattern]
    inherit_global: bool = True

    def matches_context(self, context: Dict[str, Any]) -> bool:
        """Check whether this scoped policy applies to the given context."""
        if not self.scope:
            return False

        for key, expected in self.scope.items():
            expected_value = str(expected or "*").strip()
            if expected_value in {"", "*"}:
                continue

            actual = str(context.get(key, "")).strip()
            if not fnmatch(actual, expected_value):
                return False

        return True

    def specificity(self) -> int:
        """Higher specificity wins when multiple scoped rules match."""
        return sum(
            1
            for value in self.scope.values()
            if str(value or "*").strip() not in {"", "*"}
        )


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
        self.audit_log_path = self.config_path.with_suffix('.audit.jsonl')
        self.policy: Dict[str, Any] = {}
        self.allowlist: List[CommandPattern] = []
        self.denylist: List[CommandPattern] = []
        self.scoped_policies: List[ScopedPolicy] = []
        self.config_hash: str = ""

        # Load and verify configuration
        self._load_policy()
        self._verify_integrity()

    def check_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> ApprovalDecision:
        """
        Check if command should be allowed, denied, or requires user approval.

        Args:
            command: Command to check
            context: Optional execution context (channel, agent_id, tool, etc.)

        Returns:
            ApprovalDecision (ALLOW, DENY, or ASK)
        """
        context = context or {}

        # Verify config integrity before each check
        if not self._verify_integrity():
            logger.critical("Config integrity check failed - denying all commands")
            self._append_audit_entry(
                command=command,
                decision=ApprovalDecision.DENY,
                reason="integrity_check_failed",
                context=context,
                policy_name="integrity-fail-safe",
            )
            return ApprovalDecision.DENY

        active_policy_name = "global"
        policy_mode = self.policy.get('policy', 'ask')
        allowlist = list(self.allowlist)
        denylist = list(self.denylist)

        scoped_policy = self._resolve_scoped_policy(context)
        if scoped_policy:
            active_policy_name = scoped_policy.name
            policy_mode = scoped_policy.policy or policy_mode
            if scoped_policy.inherit_global:
                allowlist.extend(scoped_policy.allowlist)
                denylist.extend(scoped_policy.denylist)
            else:
                allowlist = list(scoped_policy.allowlist)
                denylist = list(scoped_policy.denylist)

        # Check denylist first (highest priority)
        for pattern in denylist:
            if pattern.matches(command):
                logger.warning(
                    f"Command denied by denylist: {command} "
                    f"(matched: {pattern.pattern})"
                )
                self._append_audit_entry(
                    command=command,
                    decision=ApprovalDecision.DENY,
                    reason="matched_denylist",
                    context=context,
                    matched_pattern=pattern.pattern,
                    policy_name=active_policy_name,
                )
                return ApprovalDecision.DENY

        if policy_mode == 'deny':
            # Deny all commands
            self._append_audit_entry(
                command=command,
                decision=ApprovalDecision.DENY,
                reason="policy_mode_deny",
                context=context,
                policy_name=active_policy_name,
            )
            return ApprovalDecision.DENY

        elif policy_mode == 'allowlist':
            # Check allowlist
            for pattern in allowlist:
                if pattern.matches(command):
                    logger.info(
                        f"Command allowed by allowlist: {command} "
                        f"(matched: {pattern.pattern})"
                    )
                    self._append_audit_entry(
                        command=command,
                        decision=ApprovalDecision.ALLOW,
                        reason="matched_allowlist",
                        context=context,
                        matched_pattern=pattern.pattern,
                        policy_name=active_policy_name,
                    )
                    return ApprovalDecision.ALLOW

            # Not in allowlist - ask user
            self._append_audit_entry(
                command=command,
                decision=ApprovalDecision.ASK,
                reason="allowlist_miss",
                context=context,
                policy_name=active_policy_name,
            )
            return ApprovalDecision.ASK

        else:  # policy_mode == 'ask' (default)
            # Ask user for all commands
            self._append_audit_entry(
                command=command,
                decision=ApprovalDecision.ASK,
                reason="policy_mode_ask",
                context=context,
                policy_name=active_policy_name,
            )
            return ApprovalDecision.ASK

    def _load_policy(self) -> None:
        """Load policy from config file."""
        try:
            if not self.config_path.exists():
                # Create default config
                self._create_default_config()

            with open(self.config_path) as f:
                self.policy = yaml.safe_load(f) or {}

            # Parse global allowlist/denylist patterns
            self.allowlist = self._parse_patterns(self.policy.get('allowlist', []))
            self.denylist = self._parse_patterns(self.policy.get('denylist', []))

            # Parse scoped policy matrix (per-channel/per-agent/per-tool)
            self.scoped_policies = []
            for item in self.policy.get('scoped_policies', []) or []:
                if not isinstance(item, dict):
                    continue
                scoped = ScopedPolicy(
                    name=str(item.get('name') or f"scoped-{len(self.scoped_policies) + 1}"),
                    scope=dict(item.get('scope') or {}),
                    policy=str(item.get('policy') or self.policy.get('policy', 'ask')),
                    allowlist=self._parse_patterns(item.get('allowlist', []) or []),
                    denylist=self._parse_patterns(item.get('denylist', []) or []),
                    inherit_global=bool(item.get('inherit_global', True)),
                )
                self.scoped_policies.append(scoped)

            # Compute and store hash
            self.config_hash = self._compute_hash()
            self._save_hash()

            logger.info(
                f"Loaded command firewall policy: {self.policy.get('policy', 'ask')} "
                f"({len(self.allowlist)} allowed, {len(self.denylist)} denied, "
                f"{len(self.scoped_policies)} scoped)"
            )

        except Exception as e:
            logger.error(f"Error loading command firewall policy: {e}")
            # Fail-safe: deny all commands
            self.policy = {'policy': 'deny'}
            self.allowlist = []
            self.denylist = []
            self.scoped_policies = []

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
            ],
            'scoped_policies': []
        }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Created default command firewall config at {self.config_path}")

    def _parse_patterns(self, items: List[Any]) -> List[CommandPattern]:
        """Parse list of pattern objects into compiled CommandPattern entries."""
        patterns: List[CommandPattern] = []
        for item in items or []:
            if isinstance(item, str):
                pattern = item.strip()
                description = ""
            elif isinstance(item, dict):
                pattern = str(item.get('pattern', '')).strip()
                description = str(item.get('description', ''))
            else:
                continue

            if not pattern:
                continue
            patterns.append(CommandPattern(pattern=pattern, description=description))
        return patterns

    def _resolve_scoped_policy(self, context: Dict[str, Any]) -> Optional[ScopedPolicy]:
        """Find best matching scoped policy for the provided context."""
        if not context:
            return None

        matches = [policy for policy in self.scoped_policies if policy.matches_context(context)]
        if not matches:
            return None

        matches.sort(key=lambda p: p.specificity(), reverse=True)
        return matches[0]

    def _append_audit_entry(
        self,
        command: str,
        decision: ApprovalDecision,
        reason: str,
        context: Optional[Dict[str, Any]] = None,
        matched_pattern: str | None = None,
        policy_name: str | None = None,
    ) -> None:
        """Append one audit event to JSONL log file."""
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "decision": decision.value,
            "reason": reason,
            "policy": policy_name or "global",
            "context": context or {},
        }
        if matched_pattern:
            payload["matched_pattern"] = matched_pattern

        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, separators=(",", ":")) + "\n")
        except Exception as e:
            logger.error(f"Failed writing approval audit log: {e}")

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
            'scoped_policy_count': len(self.scoped_policies),
            'config_path': str(self.config_path),
            'audit_log_path': str(self.audit_log_path),
            'integrity_verified': self._verify_integrity()
        }

    def list_scoped_policies(self) -> List[Dict[str, Any]]:
        """List scoped policy entries in normalized representation."""
        result: List[Dict[str, Any]] = []
        for item in self.scoped_policies:
            result.append(
                {
                    "name": item.name,
                    "scope": dict(item.scope),
                    "policy": item.policy,
                    "allowlist_count": len(item.allowlist),
                    "denylist_count": len(item.denylist),
                    "inherit_global": item.inherit_global,
                }
            )
        return result

    def add_scoped_policy(
        self,
        name: str,
        scope: Dict[str, str],
        policy: str,
        allowlist: Optional[List[Dict[str, str]]] = None,
        denylist: Optional[List[Dict[str, str]]] = None,
        inherit_global: bool = True,
        replace: bool = False,
    ) -> bool:
        """Add or replace a scoped policy entry in config."""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f) or {}

            if policy not in {"allowlist", "ask", "deny"}:
                raise ValueError(f"Invalid policy mode: {policy}")

            scoped = list(config.get("scoped_policies", []) or [])
            existing_idx = None
            for idx, entry in enumerate(scoped):
                if isinstance(entry, dict) and str(entry.get("name", "")) == name:
                    existing_idx = idx
                    break

            if existing_idx is not None and not replace:
                logger.warning(f"Scoped policy '{name}' already exists")
                return False

            entry = {
                "name": name,
                "scope": dict(scope),
                "policy": policy,
                "inherit_global": bool(inherit_global),
                "allowlist": allowlist or [],
                "denylist": denylist or [],
            }

            if existing_idx is not None:
                scoped[existing_idx] = entry
            else:
                scoped.append(entry)

            config["scoped_policies"] = scoped

            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            self._load_policy()
            logger.info(f"Scoped policy saved: {name}")
            return True
        except Exception as e:
            logger.error(f"Error adding scoped policy '{name}': {e}")
            return False

    def remove_scoped_policy(self, name: str) -> bool:
        """Remove a scoped policy entry by name."""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f) or {}

            scoped = list(config.get("scoped_policies", []) or [])
            kept = []
            removed = False
            for entry in scoped:
                if isinstance(entry, dict) and str(entry.get("name", "")) == name:
                    removed = True
                    continue
                kept.append(entry)

            if not removed:
                return False

            config["scoped_policies"] = kept
            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            self._load_policy()
            logger.info(f"Scoped policy removed: {name}")
            return True
        except Exception as e:
            logger.error(f"Error removing scoped policy '{name}': {e}")
            return False

    def get_recent_audit(
        self,
        limit: int = 50,
        decision: str | None = None,
        channel: str | None = None,
        agent_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Read recent audit entries, newest first."""
        if limit <= 0 or not self.audit_log_path.exists():
            return []

        normalized_decision = decision.lower() if decision else None
        entries: List[Dict[str, Any]] = []

        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Failed reading approval audit log: {e}")
            return []

        for line in reversed(lines):
            if len(entries) >= limit:
                break
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue

            item_decision = str(item.get("decision", "")).lower()
            context = item.get("context") or {}

            if normalized_decision and item_decision != normalized_decision:
                continue
            if channel and str(context.get("channel", "")) != channel:
                continue
            if agent_id and str(context.get("agent_id", "")) != agent_id:
                continue

            entries.append(item)

        return entries

    def clear_audit(self) -> None:
        """Clear audit log file if present."""
        try:
            if self.audit_log_path.exists():
                self.audit_log_path.unlink()
        except Exception as e:
            logger.error(f"Failed clearing approval audit log: {e}")

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
