
import asyncio
import sys
from pathlib import Path

# Add project root to path so we can import kabot
sys.path.insert(0, str(Path(__file__).parent.parent))

from kabot.cron.service import CronService
from kabot.agent.tools.cron import CronTool
from kabot.agent.tools.registry import ToolRegistry

# Mock classes
class MockBus:
    pass

async def mock_agent_handler(job):
    print(f"\n[JOB FIRED] Job ID: {job.id}, Message: {job.payload.message}")
    return "Job executed"

async def main():
    print("Testing ToolRegistry and CronTool context...")
    
    # 1. Setup Service & Registry
    cron = CronService(Path("./test_loop_cron.json"), on_job=mock_agent_handler)
    registry = ToolRegistry(bus=MockBus())
    
    # 2. Register CronTool
    tool_instance = CronTool(cron)
    registry.register(tool_instance)
    
    # 3. Verify initial state
    retrieved_tool = registry.get("cron")
    print(f"Initial context: channel={retrieved_tool._channel}, chat_id={retrieved_tool._chat_id}")
    
    # 4. Simulate _init_session setting context
    print("Simulating _init_session context setting...")
    retrieved_tool.set_context("cli", "direct")
    
    # 5. Verify state update
    print(f"Updated context: channel={retrieved_tool._channel}, chat_id={retrieved_tool._chat_id}")
    
    if retrieved_tool._channel == "cli" and retrieved_tool._chat_id == "direct":
        print("SUCCESS: Tool context updated correctly in registry instance.")
    else:
        print("FAILURE: Tool context did NOT update.")

if __name__ == "__main__":
    asyncio.run(main())
