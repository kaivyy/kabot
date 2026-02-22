"""Tests for AutoPlanner execution with tool registry."""

from unittest.mock import AsyncMock, Mock

import pytest

from kabot.agent.tools.autoplanner import AutoPlanner, Plan, Step


class MockTool:
    """Mock tool for testing."""

    def __init__(self, name, return_value=None, should_fail=False):
        self.name = name
        self.return_value = return_value or f"Result from {name}"
        self.should_fail = should_fail
        self.execute = AsyncMock()

        if should_fail:
            self.execute.side_effect = Exception(f"Error in {name}")
        else:
            self.execute.return_value = self.return_value


class MockToolRegistry:
    """Mock tool registry for testing."""

    def __init__(self):
        self._tools = {}

    def register(self, tool):
        """Register a mock tool."""
        self._tools[tool.name] = tool

    def get(self, name):
        """Get a tool by name."""
        return self._tools.get(name)

    def has(self, name):
        """Check if tool exists."""
        return name in self._tools


class MockMessageBus:
    """Mock message bus for testing."""

    def __init__(self):
        self.messages = []
        self.outbound = Mock()
        self.outbound.put = AsyncMock()

    async def publish_outbound(self, msg):
        """Capture published messages."""
        self.messages.append(msg)


@pytest.mark.asyncio
async def test_autoplanner_executes_tool_via_registry():
    """Test that AutoPlanner can execute a tool through the registry."""
    # Create mock registry with a tool
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("read_file", return_value="file content")
    mock_registry.register(mock_tool)

    # Create planner with registry
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create a plan with one step
    plan = Plan(steps=[Step(tool="read_file", params={"path": "test.txt"})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify success
    assert result.success is True
    assert "Successfully executed 1 steps" in result.output

    # Verify tool was called
    mock_tool.execute.assert_called_once_with(path="test.txt")


@pytest.mark.asyncio
async def test_autoplanner_executes_multiple_steps():
    """Test that AutoPlanner executes multiple steps in sequence."""
    # Create mock registry with multiple tools
    mock_registry = MockToolRegistry()
    read_tool = MockTool("read_file", return_value="file content")
    count_tool = MockTool("count_lines", return_value="5")

    mock_registry.register(read_tool)
    mock_registry.register(count_tool)

    # Create planner with registry
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create a plan with two steps
    plan = Plan(steps=[
        Step(tool="read_file", params={"path": "test.txt"}),
        Step(tool="count_lines", params={"text": "file content"})
    ])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify success
    assert result.success is True
    assert "Successfully executed 2 steps" in result.output

    # Verify both tools were called
    read_tool.execute.assert_called_once_with(path="test.txt")
    count_tool.execute.assert_called_once_with(text="file content")


@pytest.mark.asyncio
async def test_autoplanner_tool_not_found():
    """Test that AutoPlanner handles missing tools."""
    # Create empty mock registry
    mock_registry = MockToolRegistry()

    # Create planner with registry
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create a plan with a non-existent tool
    plan = Plan(steps=[Step(tool="nonexistent_tool", params={})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify failure
    assert result.success is False
    assert "Tool 'nonexistent_tool' not found" in result.error


@pytest.mark.asyncio
async def test_autoplanner_execution_error():
    """Test that AutoPlanner handles tool execution errors."""
    # Create mock registry with a failing tool
    mock_registry = MockToolRegistry()
    failing_tool = MockTool("failing_tool", should_fail=True)
    mock_registry.register(failing_tool)

    # Create planner with registry
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create a plan with the failing tool
    plan = Plan(steps=[Step(tool="failing_tool", params={"param": "value"})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify failure
    assert result.success is False
    assert "Error in failing_tool" in result.error

    # Verify tool was called
    failing_tool.execute.assert_called_once_with(param="value")


@pytest.mark.asyncio
async def test_autoplanner_no_registry():
    """Test that AutoPlanner fails gracefully without a registry."""
    # Create planner without registry
    planner = AutoPlanner()

    # Create a plan
    plan = Plan(steps=[Step(tool="read_file", params={"path": "test.txt"})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify failure
    assert result.success is False
    assert "No tool registry available" in result.error


@pytest.mark.asyncio
async def test_autoplanner_empty_plan():
    """Test that AutoPlanner handles empty plans."""
    # Create mock registry
    mock_registry = MockToolRegistry()

    # Create planner with registry
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create an empty plan
    plan = Plan(steps=[])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify success with no steps
    assert result.success is True
    assert "No steps to execute" in result.output


@pytest.mark.asyncio
async def test_autoplanner_reports_progress():
    """Test that AutoPlanner reports progress via message bus."""
    # Create mock registry and message bus
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("echo", return_value="hello")
    mock_registry.register(mock_tool)

    mock_bus = MockMessageBus()

    # Create planner with both
    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus)

    # Create a plan
    plan = Plan(steps=[Step(tool="echo", params={"message": "hello"})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify success
    assert result.success is True

    # Verify progress was reported
    assert len(mock_bus.messages) > 0

    # Check for step progress message
    step_messages = [msg for msg in mock_bus.messages if "Step 1/1" in msg.content]
    assert len(step_messages) >= 1


@pytest.mark.asyncio
async def test_autoplanner_reports_step_completion():
    """Test that AutoPlanner reports step completion."""
    # Create mock registry and message bus
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("read_file", return_value="content")
    mock_registry.register(mock_tool)

    mock_bus = MockMessageBus()

    # Create planner with both
    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus)

    # Create a plan
    plan = Plan(steps=[Step(tool="read_file", params={"path": "test.txt"})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify success
    assert result.success is True

    # Verify completion was reported
    completion_messages = [msg for msg in mock_bus.messages
                          if "completed successfully" in msg.content]
    assert len(completion_messages) >= 1


@pytest.mark.asyncio
async def test_autoplanner_reports_failure():
    """Test that AutoPlanner reports step failures."""
    # Create mock registry with failing tool
    mock_registry = MockToolRegistry()
    failing_tool = MockTool("failing_tool", should_fail=True)
    mock_registry.register(failing_tool)

    mock_bus = MockMessageBus()

    # Create planner with both
    planner = AutoPlanner(tool_registry=mock_registry, message_bus=mock_bus)

    # Create a plan
    plan = Plan(steps=[Step(tool="failing_tool", params={})])

    # Execute the plan
    result = await planner.execute_plan(plan)

    # Verify failure
    assert result.success is False

    # Verify failure was reported
    failure_messages = [msg for msg in mock_bus.messages if "failed" in msg.content]
    assert len(failure_messages) >= 1


@pytest.mark.asyncio
async def test_execute_step_directly():
    """Test executing a single step directly."""
    # Create mock registry
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("echo", return_value="test output")
    mock_registry.register(mock_tool)

    # Create planner
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create a step
    step = Step(tool="echo", params={"message": "test"})

    # Execute the step
    result = await planner.execute_step(step)

    # Verify success
    assert result.success is True
    assert result.output == "test output"

    # Verify tool was called
    mock_tool.execute.assert_called_once_with(message="test")


@pytest.mark.asyncio
async def test_execute_step_no_registry():
    """Test that execute_step fails without registry."""
    # Create planner without registry
    planner = AutoPlanner()

    # Create a step
    step = Step(tool="echo", params={"message": "test"})

    # Execute the step
    result = await planner.execute_step(step)

    # Verify failure
    assert result.success is False
    assert "No tool registry available" in result.error


@pytest.mark.asyncio
async def test_execute_step_tool_not_found():
    """Test that execute_step fails for missing tool."""
    # Create empty mock registry
    mock_registry = MockToolRegistry()

    # Create planner
    planner = AutoPlanner(tool_registry=mock_registry)

    # Create a step with non-existent tool
    step = Step(tool="nonexistent", params={})

    # Execute the step
    result = await planner.execute_step(step)

    # Verify failure
    assert result.success is False
    assert "Tool 'nonexistent' not found" in result.error
