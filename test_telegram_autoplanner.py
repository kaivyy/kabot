"""Test AutoPlanner integration - Simulasi Telegram"""

import asyncio
from pathlib import Path
from kabot.agent.tools.autoplanner import AutoPlanner, Plan, Step
from kabot.agent.tools.registry import ToolRegistry
from kabot.agent.tools.filesystem import ReadFileTool, WriteFileTool
from kabot.agent.tools.shell import ExecTool
from kabot.agent.tools.utils import CountLinesTool, EchoTool

class MockMessageBus:
    """Simulasi MessageBus untuk testing"""
    def __init__(self):
        self.messages = []
        self.responses = []

    async def publish_outbound(self, message):
        self.messages.append(message)
        print(f"[BOT]: {message.content}")

    async def consume_inbound(self):
        # Simulasi response dari user
        if self.responses:
            return self.responses.pop(0)
        await asyncio.sleep(0.1)
        return None

    def add_user_response(self, response):
        self.responses.append(response)

async def test_simple_goal():
    """Test: Baca file dan hitung baris"""
    print("=" * 60)
    print("TEST 1: Simple Goal - Read and Count Lines")
    print("=" * 60)

    # Setup
    bus = MockMessageBus()
    registry = ToolRegistry()

    # Register tools
    registry.register(ReadFileTool())
    registry.register(ExecTool(working_dir=str(Path.cwd())))
    registry.register(CountLinesTool())
    registry.register(EchoTool())

    # Create AutoPlanner
    planner = AutoPlanner(tool_registry=registry, message_bus=bus)

    # Test goal
    goal = "Read file README.md and count lines"
    print(f"\n[USER] (Telegram): {goal}\n")

    # Execute
    result = await planner.execute_goal(goal)

    print(f"\n[RESULT]:")
    print(f"   Success: {result.success}")
    print(f"   Output: {result.output}")
    if result.error:
        print(f"   Error: {result.error}")

    return result.success

async def test_multi_step_workflow():
    """Test: Workflow dengan multiple steps"""
    print("\n" + "=" * 60)
    print("TEST 2: Multi-Step Workflow")
    print("=" * 60)

    bus = MockMessageBus()
    registry = ToolRegistry()

    # Register tools
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ExecTool(working_dir=str(Path.cwd())))

    planner = AutoPlanner(tool_registry=registry, message_bus=bus)

    # Test goal
    goal = "Create test file hello.txt with content 'Hello World' then read it back"
    print(f"\n[USER] (Telegram): {goal}\n")

    # Execute
    result = await planner.execute_goal(goal)

    print(f"\n[RESULT]:")
    print(f"   Success: {result.success}")
    print(f"   Output: {result.output}")

    return result.success

async def test_destructive_with_confirmation():
    """Test: Destructive action dengan confirmation"""
    print("\n" + "=" * 60)
    print("TEST 3: Destructive Action with User Confirmation")
    print("=" * 60)

    bus = MockMessageBus()

    # Simulate user response "ya" untuk konfirmasi
    bus.add_user_response(type('Msg', (), {'content': 'ya'})())

    registry = ToolRegistry()
    registry.register(WriteFileTool())
    registry.register(ExecTool(working_dir=str(Path.cwd())))
    registry.register(EchoTool())

    planner = AutoPlanner(
        tool_registry=registry,
        message_bus=bus,
        confirm_destructive=True  # Enable confirmation
    )

    # Buat file dulu untuk di-edit
    test_file = Path("test_config.txt")
    test_file.write_text("OLD CONFIG")

    goal = f"Edit file {test_file} and replace with 'NEW CONFIG'"
    print(f"\n[USER] (Telegram): {goal}")
    print("[BOT]: Meminta konfirmasi...\n")

    # Execute
    result = await planner.execute_goal(goal)

    print(f"\n[RESULT]:")
    print(f"   Success: {result.success}")
    print(f"   Output: {result.output}")

    # Cleanup
    if test_file.exists():
        test_file.unlink()

    return result.success

async def test_error_handling():
    """Test: Error handling untuk file tidak ada"""
    print("\n" + "=" * 60)
    print("TEST 4: Error Handling - File Not Found")
    print("=" * 60)

    bus = MockMessageBus()
    registry = ToolRegistry()
    registry.register(ReadFileTool())

    planner = AutoPlanner(tool_registry=registry, message_bus=bus)

    goal = "Read file yang_tidak_ada.txt"
    print(f"\n[USER] (Telegram): {goal}\n")

    # Execute
    result = await planner.execute_goal(goal)

    print(f"\n[RESULT]:")
    print(f"   Success: {result.success}")
    print(f"   Output: {result.output}")

    # Check if output contains error message (ReadFileTool returns error string, not exception)
    return "Error" in result.output or not result.success

async def main():
    print("\n" + "=" * 60)
    print("AutoPlanner Telegram Integration Test")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Simple Goal", await test_simple_goal()))
    results.append(("Multi-Step Workflow", await test_multi_step_workflow()))
    results.append(("Destructive + Confirmation", await test_destructive_with_confirmation()))
    results.append(("Error Handling", await test_error_handling()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")

    total_pass = sum(1 for _, success in results if success)
    print(f"\nTotal: {total_pass}/{len(results)} tests passed")

    if total_pass == len(results):
        print("\n[SUKSES] All tests passed! AutoPlanner ready for Telegram!")

    return total_pass == len(results)

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
