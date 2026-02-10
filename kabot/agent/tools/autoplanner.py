"""AutoPlanner tool for autonomous task execution.

This module provides the AutoPlanner class which can break down high-level goals
into executable steps using existing tools.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from kabot.agent.tools.base import Tool
from kabot.agent.tools.registry import ToolRegistry
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.bus.queue import MessageBus
from loguru import logger

# Tool name constants
TOOL_READ_FILE = "read_file"
TOOL_SHELL = "shell"
TOOL_COUNT_LINES = "count_lines"
TOOL_ECHO = "echo"

# Destructive tools that require user confirmation
DESTRUCTIVE_TOOLS = {"write_file", "edit_file", "delete_file", "exec", "cron"}


@dataclass
class Step:
    """Represents one tool execution step.

    Attributes:
        tool: Name of the tool to execute
        params: Parameters to pass to the tool
        description: Human-readable description of what this step does
    """
    tool: str
    params: dict[str, Any]
    description: str = ""


@dataclass
class Plan:
    """Contains a list of steps to execute.

    Attributes:
        steps: List of Step objects to execute sequentially
    """
    steps: list[Step] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of executing a step or plan.

    Attributes:
        success: Whether the execution was successful
        output: Output from the execution
        retry_count: Number of retries attempted
        error: Error message if execution failed
    """
    success: bool
    output: str = ""
    retry_count: int = 0
    error: str | None = None


class AutoPlanner(Tool):
    """Main orchestrator for autonomous task execution.

    The AutoPlanner can:
    - Receive natural language goals
    - Create execution plans with multiple steps
    - Execute steps sequentially using existing tools
    - Handle errors and report progress
    """

    name = "autoplanner"
    description = "Execute multi-step autonomous tasks from a natural language goal"
    parameters = {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "Natural language description of the task to execute"
            }
        },
        "required": ["goal"]
    }

    def __init__(self, tool_registry: ToolRegistry = None, message_bus: MessageBus = None, confirm_destructive: bool = True):
        """Initialize the AutoPlanner.

        Args:
            tool_registry: Optional ToolRegistry for executing tools
            message_bus: Optional MessageBus for progress reporting
            confirm_destructive: Whether to ask for confirmation before destructive actions
        """
        self.registry = tool_registry
        self.bus = message_bus
        self.confirm_destructive = confirm_destructive
        self._confirmation_timeout = 300  # 5 minutes in seconds
        self._timeout_occurred = False

    async def create_plan(self, goal: str) -> Plan:
        """Create a plan from a natural language goal.

        For now, this uses a simple mock implementation that parses
        common task patterns and creates appropriate steps.

        Args:
            goal: Natural language description of the task

        Returns:
            Plan object containing the steps to execute

        Raises:
            ValueError: If goal is empty or invalid
        """
        # Input validation
        if not goal or not goal.strip():
            raise ValueError("Goal cannot be empty or whitespace")

        if len(goal) > 1000:
            raise ValueError("Goal exceeds maximum length of 1000 characters")

        try:
            return self._parse_goal(goal)
        except Exception as e:
            # If parsing fails, raise ValueError with meaningful message
            raise ValueError(f"Failed to parse goal: {str(e)}") from e

    def _parse_goal(self, goal: str) -> Plan:
        """Parse the goal and create a plan.

        Args:
            goal: Natural language description of the task

        Returns:
            Plan object containing the steps to execute
        """
        goal_lower = goal.lower()
        steps: list[Step] = []

        # Handle "read file and count lines" pattern
        if "read" in goal_lower and "file" in goal_lower:
            filename = self._extract_filename(goal)

            if not filename:
                raise ValueError("Could not extract filename from goal")

            steps.append(Step(
                tool=TOOL_READ_FILE,
                params={"path": filename},
                description=f"Read file {filename}"
            ))

            if "count" in goal_lower and "lines" in goal_lower:
                steps.append(Step(
                    tool=TOOL_COUNT_LINES,
                    params={"text": "{{output}}"},
                    description="Count lines in file"
                ))

        # Handle "execute shell command" pattern
        elif "shell" in goal_lower or "execute" in goal_lower or "run" in goal_lower:
            cmd = self._extract_command(goal)

            if not cmd:
                raise ValueError("Could not extract shell command from goal")

            steps.append(Step(
                tool=TOOL_SHELL,
                params={"command": cmd},
                description=f"Execute shell command '{cmd}'"
            ))

        # Default: create a generic step
        if not steps:
            steps.append(Step(
                tool=TOOL_ECHO,
                params={"message": goal},
                description=f"Process goal: {goal}"
            ))

        return Plan(steps=steps)

    def _extract_filename(self, goal: str) -> str | None:
        """Extract filename from goal using regex.

        Handles filenames with dots, spaces, and special characters.
        Supports quoted filenames.

        Args:
            goal: The natural language goal

        Returns:
            Extracted filename or None if not found
        """
        # Try to find quoted filename first (single or double quotes)
        quote_pattern = r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']'
        match = re.search(quote_pattern, goal)
        if match:
            return match.group(1)

        # Try to find unquoted filename with extension
        # Matches word characters, dots, hyphens, underscores before extension (no spaces)
        unquoted_pattern = r'\b([\w.-]+\.[a-zA-Z0-9]{1,10})\b'
        match = re.search(unquoted_pattern, goal)
        if match:
            return match.group(1).strip()

        return None

    def _extract_command(self, goal: str) -> str | None:
        """Extract shell command from goal.

        Args:
            goal: The natural language goal

        Returns:
            Extracted command or None if not found
        """
        # Try to find quoted command first
        quote_pattern = r'["\']([^"\']+)["\']'
        match = re.search(quote_pattern, goal)
        if match:
            return match.group(1)

        return None

    def _should_confirm(self, step: Step) -> bool:
        """Check if a step requires user confirmation.

        Args:
            step: Step to check

        Returns:
            True if confirmation is required, False otherwise
        """
        if not self.confirm_destructive:
            return False
        return step.tool in DESTRUCTIVE_TOOLS

    def _format_confirmation_message(self, step: Step) -> str:
        """Format a confirmation message for a destructive step.

        Args:
            step: Step to format message for

        Returns:
            Formatted confirmation message in Indonesian
        """
        action_descriptions = {
            "write_file": f"menulis file",
            "edit_file": f"mengedit file",
            "delete_file": f"menghapus file",
            "exec": f"menjalankan perintah shell",
            "cron": f"mengatur jadwal cron"
        }

        action = action_descriptions.get(step.tool, f"melakukan {step.tool}")

        # Add specific details based on tool type
        details = ""
        if step.tool in ["write_file", "edit_file", "delete_file"]:
            if "path" in step.params:
                details = f" '{step.params['path']}'"
        elif step.tool == "exec":
            if "command" in step.params:
                details = f" '{step.params['command']}'"
        elif step.tool == "cron":
            if "schedule" in step.params:
                details = f" dengan jadwal '{step.params['schedule']}'"

        return f"AutoPlanner ingin {action}{details}. Setuju? (ya/tidak)"

    async def _request_confirmation(self, step: Step) -> bool:
        """Request user confirmation for a destructive step.

        Args:
            step: Step to request confirmation for

        Returns:
            True if user confirmed, False otherwise
        """
        # Reset timeout flag
        self._timeout_occurred = False

        if not self.bus:
            logger.warning("No message bus available for confirmation, proceeding without confirmation")
            return True

        # Send confirmation request
        message = self._format_confirmation_message(step)
        outbound_msg = OutboundMessage(
            channel="autoplanner",
            chat_id="autoplanner",
            content=message,
            metadata={"type": "confirmation_request", "tool": step.tool, "params": step.params}
        )

        try:
            await self.bus.publish_outbound(outbound_msg)
            logger.info(f"Confirmation request sent for {step.tool}")

            # Wait for user response with timeout
            # This assumes the message bus has a way to receive inbound messages
            # We'll poll the inbound queue for responses
            start_time = asyncio.get_event_loop().time()

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                remaining = self._confirmation_timeout - elapsed

                if remaining <= 0:
                    logger.warning(f"Confirmation timeout for {step.tool}")
                    # Send timeout message
                    timeout_msg = OutboundMessage(
                        channel="autoplanner",
                        chat_id="autoplanner",
                        content="Timeout, eksekusi dibatalkan",
                        metadata={"type": "timeout", "tool": step.tool}
                    )
                    await self.bus.publish_outbound(timeout_msg)
                    self._timeout_occurred = True
                    return False

                try:
                    # Wait for a message with timeout
                    msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=min(1.0, remaining))

                    # Check if this is a response to our confirmation request
                    if msg and msg.content:
                        response = msg.content.strip().lower()

                        if response in ["ya", "yes", "y", "setuju"]:
                            logger.info(f"User confirmed {step.tool}")
                            return True
                        elif response in ["tidak", "no", "n", "batal", "cancel"]:
                            logger.info(f"User rejected {step.tool}")
                            # Send cancellation message
                            cancel_msg = OutboundMessage(
                                channel="autoplanner",
                                chat_id="autoplanner",
                                content="Dibatalkan oleh user",
                                metadata={"type": "cancelled", "tool": step.tool}
                            )
                            await self.bus.publish_outbound(cancel_msg)
                            return False
                        # If not a clear response, continue waiting

                except asyncio.TimeoutError:
                    # No message received yet, continue loop
                    continue
                except Exception as e:
                    logger.error(f"Error waiting for confirmation: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error requesting confirmation: {e}")
            # In case of error, proceed without confirmation for safety
            return False

        return False

    async def execute_plan(self, plan: Plan) -> ExecutionResult:
        """Execute a plan sequentially.

        Args:
            plan: Plan object containing steps to execute

        Returns:
            ExecutionResult with success/failure status
        """
        if not plan.steps:
            return ExecutionResult(
                success=True,
                output="No steps to execute",
                retry_count=0
            )

        # Report plan start
        await self._report_progress(f"Starting plan execution with {len(plan.steps)} steps", 0, len(plan.steps))

        for i, step in enumerate(plan.steps):
            # Report step start
            await self._report_progress(f"Executing step {i+1}/{len(plan.steps)}: {step.tool}", i+1, len(plan.steps))

            # Check if confirmation is needed for destructive actions
            if self._should_confirm(step):
                confirmed = await self._request_confirmation(step)
                if not confirmed:
                    error_msg = "Timeout, eksekusi dibatalkan" if self._timeout_occurred else "Dibatalkan oleh user"
                    return ExecutionResult(
                        success=False,
                        error=error_msg,
                        retry_count=0
                    )

            # Execute step
            result = await self.execute_step(step)

            if not result.success:
                # Report failure
                await self._report_progress(f"Step {i+1} failed: {result.error}", i+1, len(plan.steps))
                return ExecutionResult(
                    success=False,
                    error=result.error,
                    retry_count=result.retry_count
                )

            # Report step completion
            await self._report_progress(f"Step {i+1} completed successfully", i+1, len(plan.steps))

        # Report plan completion
        await self._report_progress("Plan execution completed successfully", len(plan.steps), len(plan.steps))

        return ExecutionResult(
            success=True,
            output=f"Successfully executed {len(plan.steps)} steps",
            retry_count=0
        )

    async def execute_step(self, step: Step) -> ExecutionResult:
        """Execute a single step.

        Args:
            step: Step to execute

        Returns:
            ExecutionResult with success/failure status
        """
        if not self.registry:
            return ExecutionResult(
                success=False,
                error="No tool registry available",
                retry_count=0
            )

        # Look up tool in registry
        tool = self.registry.get(step.tool)
        if not tool:
            return ExecutionResult(
                success=False,
                error=f"Tool '{step.tool}' not found in registry",
                retry_count=0
            )

        try:
            # Execute tool with step parameters
            result = await tool.execute(**step.params)
            result_str = str(result)

            # Check if result contains error message
            if result_str.startswith("Error:"):
                return ExecutionResult(
                    success=False,
                    error=result_str,
                    retry_count=0
                )

            return ExecutionResult(
                success=True,
                output=result_str,
                retry_count=0
            )
        except Exception as e:
            logger.error(f"Error executing tool {step.tool}: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                retry_count=0
            )

    async def _report_progress(self, message: str, current_step: int, total_steps: int) -> None:
        """Report progress via message bus if available.

        Args:
            message: Progress message to report
            current_step: Current step number
            total_steps: Total number of steps
        """
        if self.bus:
            progress_msg = f"Step {current_step}/{total_steps}: {message}"
            outbound_msg = OutboundMessage(
                channel="autoplanner",
                chat_id="autoplanner",
                content=progress_msg,
                metadata={"current_step": current_step, "total_steps": total_steps}
            )
            await self.bus.publish_outbound(outbound_msg)

    async def execute(self, goal: str) -> str:
        """Execute the autoplanner with a natural language goal.

        This method is called by the Tool base class when the autoplanner
        is invoked through the tool registry.

        Args:
            goal: Natural language description of the task to execute

        Returns:
            String result of the execution (success or failure message)
        """
        result = await self.execute_goal(goal)
        if result.success:
            return f"Success: {result.output}"
        else:
            return f"Error: {result.error}"

    async def execute_goal(self, goal: str) -> ExecutionResult:
        """Execute a goal by creating and executing a plan.

        Args:
            goal: Natural language description of the task

        Returns:
            ExecutionResult with success/failure status
        """
        try:
            # Create plan from goal
            plan = await self.create_plan(goal)

            # Execute the plan
            result = await self.execute_plan(plan)

            return result
        except ValueError as e:
            return ExecutionResult(
                success=False,
                error=str(e),
                retry_count=0
            )
        except Exception as e:
            logger.error(f"Error executing goal: {e}")
            return ExecutionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                retry_count=0
            )
