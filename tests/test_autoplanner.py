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


@pytest.mark.asyncio
async def test_step_creation():
    """Test that Step objects can be created with correct attributes."""
    step = Step(
        tool="read_file",
        params={"path": "test.txt"},
        description="Read the test file"
    )

    assert step.tool == "read_file"
    assert step.params["path"] == "test.txt"
    assert step.description == "Read the test file"


@pytest.mark.asyncio
async def test_plan_creation():
    """Test that Plan objects can be created and hold steps."""
    step1 = Step(tool="read_file", params={"path": "test.txt"}, description="Read file")
    step2 = Step(tool="count_lines", params={"text": "content"}, description="Count lines")

    plan = Plan(steps=[step1, step2])

    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "read_file"
    assert plan.steps[1].tool == "count_lines"


@pytest.mark.asyncio
async def test_execution_result_creation():
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
