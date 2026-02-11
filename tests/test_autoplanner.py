"""Tests for the AutoPlanner module."""

import pytest
from kabot.agent.tools.autoplanner import AutoPlanner, Plan, Step, ExecutionResult


@pytest.mark.asyncio
async def test_autoplanner_can_plan_simple_task():
    """Test that AutoPlanner can create a plan for a simple task."""
    planner = AutoPlanner()
    plan = await planner.create_plan("Read file test.txt and count lines")

    assert len(plan.steps) >= 2
    assert plan.steps[0].tool == "read_file"
    assert "test.txt" in plan.steps[0].params["path"]


def test_step_creation():
    """Test that Step objects can be created with correct attributes."""
    step = Step(
        tool="read_file",
        params={"path": "test.txt"},
        description="Read the test file"
    )

    assert step.tool == "read_file"
    assert step.params["path"] == "test.txt"
    assert step.description == "Read the test file"


def test_plan_creation():
    """Test that Plan objects can be created and hold steps."""
    step1 = Step(tool="read_file", params={"path": "test.txt"}, description="Read file")
    step2 = Step(tool="count_lines", params={"text": "content"}, description="Count lines")

    plan = Plan(steps=[step1, step2])

    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "read_file"
    assert plan.steps[1].tool == "count_lines"


def test_execution_result_creation():
    """Test that ExecutionResult objects can be created."""
    result = ExecutionResult(
        success=True,
        output="File content here",
        retry_count=0
    )

    assert result.success is True
    assert result.output == "File content here"
    assert result.retry_count == 0


@pytest.mark.asyncio
async def test_autoplanner_plan_structure():
    """Test that AutoPlanner creates plans with proper structure."""
    planner = AutoPlanner()
    plan = await planner.create_plan("Execute shell command 'ls -la'")

    assert isinstance(plan, Plan)
    assert len(plan.steps) >= 1

    for step in plan.steps:
        assert isinstance(step, Step)
        assert step.tool is not None
        assert step.params is not None
        assert step.description is not None


# ============================================================================
# Error Condition Tests
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_empty_goal_raises_error():
    """Test that AutoPlanner raises ValueError for empty goal."""
    planner = AutoPlanner()

    with pytest.raises(ValueError, match="empty"):
        await planner.create_plan("")


@pytest.mark.asyncio
async def test_autoplanner_whitespace_goal_raises_error():
    """Test that AutoPlanner raises ValueError for whitespace-only goal."""
    planner = AutoPlanner()

    with pytest.raises(ValueError, match="empty"):
        await planner.create_plan("   ")


@pytest.mark.asyncio
async def test_autoplanner_long_goal_raises_error():
    """Test that AutoPlanner raises ValueError for excessively long goal."""
    planner = AutoPlanner()
    long_goal = "x" * 1001

    with pytest.raises(ValueError, match="maximum length"):
        await planner.create_plan(long_goal)


@pytest.mark.asyncio
async def test_autoplanner_missing_filename_raises_error():
    """Test that AutoPlanner raises ValueError when filename cannot be extracted."""
    planner = AutoPlanner()

    with pytest.raises(ValueError, match="filename"):
        await planner.create_plan("Read file and count lines")


@pytest.mark.asyncio
async def test_autoplanner_missing_shell_command_raises_error():
    """Test that AutoPlanner raises ValueError when shell command cannot be extracted."""
    planner = AutoPlanner()

    with pytest.raises(ValueError, match="shell command"):
        await planner.create_plan("Execute shell command")


# ============================================================================
# Edge Case Tests for Parsing
# ============================================================================

@pytest.mark.asyncio
async def test_autoplanner_filename_with_dots():
    """Test parsing filename with multiple dots."""
    planner = AutoPlanner()
    plan = await planner.create_plan("Read file my.backup.txt")

    assert plan.steps[0].params["path"] == "my.backup.txt"


@pytest.mark.asyncio
async def test_autoplanner_filename_with_spaces():
    """Test parsing filename with spaces."""
    planner = AutoPlanner()
    plan = await planner.create_plan("Read file 'file with spaces.txt'")

    assert plan.steps[0].params["path"] == "file with spaces.txt"


@pytest.mark.asyncio
async def test_autoplanner_quoted_filename():
    """Test parsing quoted filename."""
    planner = AutoPlanner()
    plan = await planner.create_plan('Read file "test.txt"')

    assert plan.steps[0].params["path"] == "test.txt"


@pytest.mark.asyncio
async def test_autoplanner_complex_shell_command():
    """Test parsing complex shell command with special characters."""
    planner = AutoPlanner()
    plan = await planner.create_plan("Execute shell command 'ls -la | grep test > output.txt'")

    assert "ls -la | grep test > output.txt" in plan.steps[0].params["command"]


# ============================================================================
# Execution Method Tests
# ============================================================================

class MockTool:
    """Mock tool for testing."""
    def __init__(self, name, return_value="mock result"):
        self.name = name
        self.return_value = return_value

    async def execute(self, **kwargs):
        return self.return_value


class MockToolRegistry:
    """Mock tool registry for testing."""
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        self._tools[tool.name] = tool

    def get(self, name):
        return self._tools.get(name)


@pytest.mark.asyncio
async def test_execute_plan_returns_result():
    """Test that execute_plan returns an ExecutionResult."""
    # Create mock registry with a tool
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("read_file", return_value="file content")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry)
    plan = Plan(steps=[
        Step(tool="read_file", params={"path": "test.txt"}, description="Read file")
    ])

    result = await planner.execute_plan(plan)

    assert isinstance(result, ExecutionResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_execute_step_returns_result():
    """Test that execute_step returns an ExecutionResult."""
    # Create mock registry with a tool
    mock_registry = MockToolRegistry()
    mock_tool = MockTool("read_file", return_value="file content")
    mock_registry.register(mock_tool)

    planner = AutoPlanner(tool_registry=mock_registry)
    step = Step(tool="read_file", params={"path": "test.txt"}, description="Read file")

    result = await planner.execute_step(step)

    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert "file content" in result.output
