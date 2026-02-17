import pytest

@pytest.mark.asyncio
async def test_send_agent_message():
    from kabot.agent.agent_comm import AgentComm, AgentMessage
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    comm = AgentComm(bus, "agent-1")

    msg = await comm.send("agent-2", {"task": "analyze code"}, msg_type="request")
    assert msg.from_agent == "agent-1"
    assert msg.to_agent == "agent-2"
    assert msg.msg_type == "request"

@pytest.mark.asyncio
async def test_receive_agent_message():
    from kabot.agent.agent_comm import AgentComm
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    comm1 = AgentComm(bus, "agent-1")
    comm2 = AgentComm(bus, "agent-2")

    # Send message
    await comm1.send("agent-2", {"task": "test"})

    # Receive message
    msg = await comm2.receive(timeout=1.0)
    assert msg.from_agent == "agent-1"
    assert msg.content["task"] == "test"
