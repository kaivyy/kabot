"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from kabot.agent.tools.base import Tool


class ExecTool(Tool):
    """Tool to execute shell commands."""
    
    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        read_only_mode: bool = False,
        docker_config: Any | None = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.read_only_mode = read_only_mode
        self.docker_config = docker_config
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"\b(format|mkfs|diskpart)\b",   # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
        ]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace

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
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        # Check for high-risk commands that always require explicit user confirmation
        if self._is_high_risk(command):
             # In a future update, we can implement an interactive confirmation loop here.
             # For now, we block it to be safe unless allow_patterns overrides it.
             if not self.allow_patterns:
                 return "Error: High-risk command blocked. Please execute this manually or add to allow_patterns."

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
                process.kill()
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
            
            return result
            
        except Exception as e:
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
