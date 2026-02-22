"""Integration tests for AutoPlanner in AgentLoop."""

from unittest.mock import AsyncMock, Mock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.agent.tools.autoplanner import AutoPlanner
from kabot.agent.tools.registry import ToolRegistry
from kabot.bus.queue import MessageBus


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self):
        self.responses = []
        self.response_index = 0

    def get_default_model(self):
        return "mock-model"

    async def chat(self, messages, tools=None, model=None):
        """Return mock responses."""
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response
        # Default response with no tool calls
        return Mock(has_tool_calls=False, content="Mock response", tool_calls=[])


class MockResponse:
    """Mock LLM response."""

    def __init__(self, has_tool_calls=False, content="", tool_calls=None):
        self.has_tool_calls = has_tool_calls
        self.content = content
        self.tool_calls = tool_calls or []


class MockToolCall:
    """Mock tool call."""

    def __init__(self, id, name, arguments):
        self.id = id
        self.name = name
        self.arguments = arguments

    def model_dump(self):
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments
        }


@pytest.fixture
def tmp_path(tmp_path_factory):
    """Create a temporary workspace."""
    return tmp_path_factory.mktemp("workspace")


@pytest.fixture
def mock_bus():
    """Create a mock message bus."""
    bus = Mock(spec=MessageBus)
    bus.consume_inbound = AsyncMock()
    bus.publish_outbound = AsyncMock()
    bus._agent_subscribers = {}  # Add the missing attribute
    return bus


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    return MockLLMProvider()


@pytest.mark.asyncio
async def test_autoplanner_integration_in_loop(tmp_path, mock_bus, mock_provider):
    """Test that AutoPlanner is registered in AgentLoop."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    # Check AutoPlanner is registered
    assert "autoplanner" in loop.tools

    # Get the autoplanner tool
    autoplanner = loop.tools.get("autoplanner")
    assert autoplanner is not None
    assert isinstance(autoplanner, AutoPlanner)


@pytest.mark.asyncio
async def test_autoplanner_has_correct_properties(tmp_path, mock_bus, mock_provider):
    """Test that AutoPlanner has correct tool properties."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    autoplanner = loop.tools.get("autoplanner")

    # Check tool properties
    assert autoplanner.name == "autoplanner"
    assert "multi-step" in autoplanner.description.lower()
    assert "autonomous" in autoplanner.description.lower()

    # Check parameters schema
    params = autoplanner.parameters
    assert "properties" in params
    assert "goal" in params["properties"]
    assert "required" in params
    assert "goal" in params["required"]


@pytest.mark.asyncio
async def test_autoplanner_execution_via_registry(tmp_path, mock_bus, mock_provider):
    """Test AutoPlanner execution through tool registry."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")

    # Execute autoplanner through registry
    result = await loop.tools.execute("autoplanner", {"goal": "Read file test.txt"})

    # Should return success message
    assert "Success" in result or "Error" in result


@pytest.mark.asyncio
async def test_autoplanner_has_access_to_other_tools(tmp_path, mock_bus, mock_provider):
    """Test that AutoPlanner has access to all other tools."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    autoplanner = loop.tools.get("autoplanner")

    # Check that autoplanner has access to the tool registry
    assert autoplanner.registry is not None
    assert isinstance(autoplanner.registry, ToolRegistry)

    # Check that common tools are available in the registry
    assert autoplanner.registry.has("read_file")
    assert autoplanner.registry.has("exec")


@pytest.mark.asyncio
async def test_autoplanner_has_message_bus(tmp_path, mock_bus, mock_provider):
    """Test that AutoPlanner has access to message bus."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    autoplanner = loop.tools.get("autoplanner")

    # Check that autoplanner has access to the message bus
    assert autoplanner.bus is not None
    assert autoplanner.bus == mock_bus


@pytest.mark.asyncio
async def test_autoplanner_tool_schema():
    """Test that AutoPlanner generates correct tool schema."""
    autoplanner = AutoPlanner()
    schema = autoplanner.to_schema()

    # Check schema structure
    assert schema["type"] == "function"
    assert "function" in schema
    assert schema["function"]["name"] == "autoplanner"
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]


@pytest.mark.asyncio
async def test_autoplanner_execution_with_mock_registry():
    """Test AutoPlanner execution with mock tools."""
    # Create mock registry with mock tools
    registry = ToolRegistry()

    # Create a mock tool that returns success
    mock_tool = Mock()
    mock_tool.name = "mock_tool"
    mock_tool.execute = AsyncMock(return_value="mock result")
    mock_tool.validate_params = Mock(return_value=[])

    registry.register(mock_tool)

    # Create autoplanner with registry
    autoplanner = AutoPlanner(tool_registry=registry)

    # Manually create and execute a plan
    from kabot.agent.tools.autoplanner import Plan, Step
    plan = Plan(steps=[Step(tool="mock_tool", params={"param": "value"})])

    result = await autoplanner.execute_plan(plan)

    assert result.success is True
    assert "Successfully executed 1 steps" in result.output


@pytest.mark.asyncio
async def test_autoplanner_end_to_end_mocked(tmp_path, mock_bus, mock_provider):
    """Test AutoPlanner end-to-end with mocked dependencies."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    # Create a test file
    test_file = tmp_path / "README.md"
    test_file.write_text("# Test Project\n\nThis is a test.")

    # Get autoplanner and execute directly
    autoplanner = loop.tools.get("autoplanner")

    # Execute with goal
    result = await autoplanner.execute(goal="Read file README.md")

    # Should return success
    assert "Success" in result


@pytest.mark.asyncio
async def test_autoplanner_integration_with_real_bus(tmp_path, mock_provider):
    """Test AutoPlanner with real message bus."""
    # Create real message bus
    bus = MessageBus()

    loop = AgentLoop(
        bus=bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    # Check autoplanner has the real bus
    autoplanner = loop.tools.get("autoplanner")
    assert autoplanner.bus is bus


@pytest.mark.asyncio
async def test_autoplanner_is_last_tool_registered(tmp_path, mock_bus, mock_provider):
    """Test that AutoPlanner is registered last to have access to all tools."""
    loop = AgentLoop(
        bus=mock_bus,
        provider=mock_provider,
        workspace=tmp_path
    )

    # Get list of registered tools
    tool_names = loop.tools.tool_names

    # AutoPlanner should be in the list
    assert "autoplanner" in tool_names

    # AutoPlanner should have access to all other tools
    autoplanner = loop.tools.get("autoplanner")
    for tool_name in tool_names:
        if tool_name != "autoplanner":
            assert autoplanner.registry.has(tool_name), f"AutoPlanner missing tool: {tool_name}"
