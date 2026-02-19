"""Shell execution tool."""

import asyncio
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Awaitable

from loguru import logger

from kabot.agent.tools.base import Tool
from kabot.security.command_firewall import CommandFirewall, ApprovalDecision

ApprovalDecisionValue = str | bool
ApprovalCallback = Callable[[str, Path], ApprovalDecisionValue | Awaitable[ApprovalDecisionValue]]


class ExecTool(Tool):
    """Tool to execute shell commands with CommandFirewall protection."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        read_only_mode: bool = False,
        docker_config: Any | None = None,
        firewall_config_path: Path | None = None,
        auto_approve: bool = False,
        approval_callback: ApprovalCallback | None = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.read_only_mode = read_only_mode
        self.docker_config = docker_config
        self.restrict_to_workspace = restrict_to_workspace
        self.auto_approve = auto_approve
        self.approval_callback = approval_callback

        # Legacy pattern support (deprecated, use CommandFirewall instead)
        self.deny_patterns = deny_patterns or []
        self.allow_patterns = allow_patterns or []
        self._always_approved_commands: set[str] = set()
        self._pending_approvals: dict[str, dict[str, Any]] = {}

        # Initialize CommandFirewall
        if firewall_config_path is None:
            # Default location: ~/.kabot/command_approvals.yaml
            firewall_config_path = Path.home() / ".kabot" / "command_approvals.yaml"

        try:
            self.firewall = CommandFirewall(firewall_config_path)
            logger.info(f"CommandFirewall initialized: {self.firewall.get_policy_info()}")
        except Exception as e:
            logger.error(f"Failed to initialize CommandFirewall: {e}")
            self.firewall = None

    def set_approval_callback(self, callback: ApprovalCallback | None) -> None:
        """Set interactive approval callback used when firewall policy returns ASK."""
        self.approval_callback = callback

    def _store_pending_approval(self, session_key: str, command: str, cwd: str) -> str:
        """Store pending approval request for later /approve handling."""
        approval_id = uuid.uuid4().hex[:8]
        self._pending_approvals[session_key] = {
            "id": approval_id,
            "command": command,
            "working_dir": cwd,
            "created_at": time.time(),
        }
        return approval_id

    def set_pending_approval(self, session_key: str, command: str, working_dir: str | None = None) -> str:
        """Public helper for tests and external approval orchestration."""
        cwd = working_dir or self.working_dir or os.getcwd()
        return self._store_pending_approval(session_key, command, cwd)

    def get_pending_approval(self, session_key: str, approval_id: str | None = None) -> dict[str, Any] | None:
        """Get pending approval for a session (optionally constrained by approval id)."""
        pending = self._pending_approvals.get(session_key)
        if not pending:
            return None
        if approval_id and pending.get("id") != approval_id:
            return None
        return dict(pending)

    def consume_pending_approval(self, session_key: str, approval_id: str | None = None) -> dict[str, Any] | None:
        """Consume pending approval and remove it from queue."""
        pending = self._pending_approvals.get(session_key)
        if not pending:
            return None
        if approval_id and pending.get("id") != approval_id:
            return None
        self._pending_approvals.pop(session_key, None)
        return dict(pending)

    def clear_pending_approval(self, session_key: str, approval_id: str | None = None) -> bool:
        """Clear pending approval without executing it."""
        pending = self._pending_approvals.get(session_key)
        if not pending:
            return False
        if approval_id and pending.get("id") != approval_id:
            return False
        self._pending_approvals.pop(session_key, None)
        return True

    @staticmethod
    def _normalize_approval_choice(choice: ApprovalDecisionValue | None) -> str:
        """Normalize callback response into one of allow_once/allow_always/deny."""
        if choice is True:
            return "allow_once"
        if choice is False or choice is None:
            return "deny"
        normalized = str(choice).strip().lower()
        if normalized in {"allow", "allow_once", "once", "yes", "y"}:
            return "allow_once"
        if normalized in {"allow_always", "always", "persist", "a"}:
            return "allow_always"
        return "deny"

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                }
            },
            "required": ["command"]
        }

    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        if self.read_only_mode:
            return "Error: Shell execution is disabled (read-only mode active)."

        cwd = working_dir or self.working_dir or os.getcwd()
        session_key = kwargs.get("_session_key") if isinstance(kwargs.get("_session_key"), str) else None
        approved_by_user = bool(kwargs.get("_approved_by_user", False))
        if command in self._always_approved_commands:
            approved_by_user = True

        # Phase 13: Use CommandFirewall for granular approval
        if self.firewall and not self.auto_approve and not approved_by_user:
            firewall_context = {
                "tool": self.name,
                "channel": kwargs.get("_channel") if isinstance(kwargs.get("_channel"), str) else "",
                "chat_id": kwargs.get("_chat_id") if isinstance(kwargs.get("_chat_id"), str) else "",
                "session_key": session_key or "",
                "agent_id": kwargs.get("_agent_id") if isinstance(kwargs.get("_agent_id"), str) else "",
                "account_id": kwargs.get("_account_id") if isinstance(kwargs.get("_account_id"), str) else "",
                "thread_id": kwargs.get("_thread_id") if isinstance(kwargs.get("_thread_id"), str) else "",
                "peer_kind": kwargs.get("_peer_kind") if isinstance(kwargs.get("_peer_kind"), str) else "",
                "peer_id": kwargs.get("_peer_id") if isinstance(kwargs.get("_peer_id"), str) else "",
            }
            decision = self.firewall.check_command(command, context=firewall_context)

            if decision == ApprovalDecision.DENY:
                logger.warning(f"Command denied by firewall: {command}")
                return (
                    f"Error: Command blocked by security policy.\n"
                    f"Command: {command}\n"
                    f"Reason: Matches denylist pattern or policy is set to 'deny'.\n"
                    f"To allow this command, add it to the allowlist in: {self.firewall.config_path}"
                )

            elif decision == ApprovalDecision.ASK:
                if self.approval_callback:
                    try:
                        callback_result = self.approval_callback(command, self.firewall.config_path)
                        if asyncio.iscoroutine(callback_result):
                            callback_result = await callback_result
                        choice = self._normalize_approval_choice(callback_result)
                        if choice == "allow_always":
                            self._always_approved_commands.add(command)
                            approved_by_user = True
                            logger.info(f"Command approved persistently by user: {command}")
                        elif choice == "allow_once":
                            approved_by_user = True
                            logger.info(f"Command approved once by user: {command}")
                        else:
                            logger.info(f"Command denied by interactive approval: {command}")
                            return (
                                "Error: Command denied by user approval.\n"
                                f"Command: {command}\n"
                                "Reason: Approval prompt returned deny."
                            )
                    except Exception as exc:
                        logger.warning(f"Approval callback failed ({exc}); falling back to pending approval flow")

                if not approved_by_user:
                    if session_key:
                        approval_id = self._store_pending_approval(session_key, command, cwd)
                        logger.info(f"Command queued for approval {approval_id}: {command}")
                        return (
                            "Error: Command requires approval by security policy.\n"
                            f"Command: {command}\n"
                            f"Approval ID: {approval_id}\n"
                            f"Reply with '/approve {approval_id}' to run once, or '/deny {approval_id}' to reject."
                        )

                    logger.info(f"Command requires approval: {command}")
                    return (
                        "Error: Command requires approval by security policy.\n"
                        f"Command: {command}\n"
                        "Reason: Firewall policy is 'ask' and no explicit approval was provided.\n"
                        "Use elevated mode, or add a strict allowlist entry in: "
                        f"{self.firewall.config_path}"
                    )

        # Legacy guard (deprecated, firewall is preferred)
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        # Check for high-risk commands that always require explicit user confirmation
        if self._is_high_risk(command):
             # In a future update, we can implement an interactive confirmation loop here.
             # For now, we block it to be safe unless allow_patterns overrides it.
             if not self.allow_patterns and not self.auto_approve and not approved_by_user:
                 return "Error: High-risk command blocked. Please execute this manually or enable elevated mode."

        try:
            # Docker Sandbox Execution
            if self.docker_config and self.docker_config.enabled:
                cwd_path = Path(cwd).resolve()
                docker_cmd = f"docker run --rm -v \"{cwd_path}:/app\" -w /app"

                if self.docker_config.network_disabled:
                    docker_cmd += " --network none"

                if self.docker_config.memory_limit:
                    docker_cmd += f" --memory {self.docker_config.memory_limit}"

                # Escape command for shell execution inside docker
                safe_cmd = command.replace('"', '\\"')
                docker_cmd += f" {self.docker_config.image} sh -c \"{safe_cmd}\""

                # Execute the docker wrapper command
                process = await asyncio.create_subprocess_shell(
                    docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                # Standard Local Execution
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                kill_result = process.kill()
                if asyncio.iscoroutine(kill_result):
                    await kill_result
                return f"Error: Command timed out after {self.timeout} seconds"

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))

            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            if process.returncode != 0:
                hint = self._get_error_hint(command, stderr_text)
                if hint:
                    output_parts.append(f"\nHINT: {hint}")
                output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"

            # Audit log successful execution
            logger.info(f"Command executed successfully: {command[:100]}")

            return result

        except Exception as e:
            logger.error(f"Command execution failed: {command[:100]} - {e}")
            return f"Error executing command: {str(e)}"

    def _get_error_hint(self, command: str, stderr: str) -> str | None:
        """Provide helpful suggestions based on failed command and platform."""
        import platform
        is_windows = platform.system() == "Windows"
        cmd = command.lower().split()[0] if command.strip() else ""
        
        # OS Mismatch Hints
        if is_windows:
            if cmd in ["ls", "grep", "cat", "touch", "rm", "cp", "mv"]:
                mapping = {
                    "ls": "dir",
                    "grep": "findstr",
                    "cat": "type",
                    "touch": "New-Item",
                    "rm": "del",
                    "cp": "copy",
                    "mv": "move"
                }
                return f"You are on Windows. Try using '{mapping.get(cmd)}' instead of '{cmd}'."
        else:
            if cmd in ["dir", "findstr", "type", "del", "copy", "move"]:
                mapping = {
                    "dir": "ls",
                    "findstr": "grep",
                    "type": "cat",
                    "del": "rm",
                    "copy": "cp",
                    "move": "mv"
                }
                return f"You are on Linux/macOS. Try using '{mapping.get(cmd)}' instead of '{cmd}'."
        
        # Common Path Errors
        if "not recognized" in stderr or "not found" in stderr:
            return f"The command '{cmd}' was not found. Check if it's installed and in your PATH."
            
        return None

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()

            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"']+", cmd)
            posix_paths = re.findall(r"/[^\s\"']+", cmd)

            for raw in win_paths + posix_paths:
                try:
                    p = Path(raw).resolve()
                except Exception:
                    continue
                if cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked by safety guard (path outside working dir)"

        return None

    def _is_high_risk(self, command: str) -> bool:
        """
        Check if command is high-risk and requires explicit confirmation.

        High-risk commands include:
        - System modifications (package installs, system updates)
        - Network operations (curl/wget with pipe to shell)
        - Privilege escalation (sudo, su)
        - Process manipulation (kill -9, pkill)

        Args:
            command: Command to check

        Returns:
            True if command is high-risk
        """
        lower = command.lower().strip()

        # Package managers and system updates
        high_risk_patterns = [
            r'\b(apt|yum|dnf|pacman|brew)\s+(install|remove|update|upgrade)',
            r'\bpip\s+install\b',
            r'\bnpm\s+(install|uninstall)\s+-g\b',
            r'\bcargo\s+install\b',

            # Privilege escalation
            r'\b(sudo|su)\b',

            # Network + shell execution
            r'(curl|wget).*\|\s*(bash|sh|python|ruby|perl)',

            # Process killing
            r'\bkill\s+-9\b',
            r'\bpkill\b',

            # System services
            r'\bsystemctl\s+(start|stop|restart|enable|disable)',
            r'\bservice\s+\w+\s+(start|stop|restart)',
        ]

        for pattern in high_risk_patterns:
            if re.search(pattern, lower):
                return True

        return False
