# Multi-Agent Orchestration System Design

**Date**: 2026-02-18
**Status**: Design Phase
**Target**: Implement advanced multi-agent orchestration with role-based model assignment

## Overview

This design implements a multi-agent orchestration system that enables:
- Multiple agents with different AI models communicating with each other
- Role-based agent assignment (Master, Brainstorming, Executor, Verifier)
- Multi-bot support (multiple Telegram/Discord bots on one server)
- User choice between single-agent and multi-agent modes
- One model can power multiple agents/bots

## Current State Analysis

**Kabot & OpenClaw Current Architecture:**
- Both only support parent-child task delegation
- No agent-to-agent peer communication
- No role-based model assignment
- Single agent per session

**Infrastructure Already Available:**
- MessageBus with 3 queues (inbound, outbound, system_events)
- SubagentManager for background task execution
- SubagentRegistry for persistent tracking
- SystemEvent bus for monitoring
- Session isolation with PIDLock

## Architecture Design

### 1. Agent Registry

**Purpose**: Track multiple agents with different roles and models

**Location**: `kabot/agent/agent_registry.py`

**Data Structure**:
```python
{
    "agents": {
        "agent-uuid-1": {
            "agent_id": "agent-uuid-1",
            "role": "master",
            "model": "openai/gpt-4o",
            "status": "active",  # active, idle, busy, stopped
            "created_at": "2026-02-18T10:00:00Z",
            "last_active": "2026-02-18T10:05:00Z",
            "capabilities": ["planning", "coordination"],
            "assigned_bots": ["telegram:123456", "discord:789012"]
        },
        "agent-uuid-2": {
            "agent_id": "agent-uuid-2",
            "role": "executor",
            "model": "moonshot/kimi-k2.5",
            "status": "busy",
            "created_at": "2026-02-18T10:01:00Z",
            "last_active": "2026-02-18T10:06:00Z",
            "capabilities": ["code_execution", "file_operations"],
            "assigned_bots": []
        }
    }
}
```

**Persistence**: `~/.kabot/agents/registry.json`

**Methods**:
- `register_agent(role, model, capabilities) -> agent_id`
- `get_agent(agent_id) -> AgentInfo`
- `list_agents(role=None, status=None) -> List[AgentInfo]`
- `update_status(agent_id, status)`
- `assign_bot(agent_id, bot_id)`
- `remove_agent(agent_id)`

### 2. Agent-to-Agent Communication Protocol

**Purpose**: Enable agents to communicate directly with each other

**Location**: `kabot/agent/agent_comm.py`

**Message Types**:
```python
class AgentMessage:
    msg_id: str
    from_agent: str
    to_agent: str | None  # None = broadcast
    msg_type: str  # request, response, broadcast, notification
    content: dict
    timestamp: str
    reply_to: str | None
```

**Communication Flow**:
1. Agent A sends message via `AgentComm.send(to_agent, content)`
2. Message routed through MessageBus with special `agent:` channel
3. Agent B receives via `AgentComm.receive()` or subscription
4. Agent B can reply with `reply_to=msg_id`

**Integration with MessageBus**:
- Add new queue: `agent_messages: asyncio.Queue[AgentMessage]`
- Agents subscribe to their own agent_id channel
- Broadcast messages go to all agents

### 3. Role-Based Model Assignment

**Purpose**: Assign specific models to agent roles

**Location**: `kabot/agent/role_manager.py`

**Role Definitions**:
```python
AGENT_ROLES = {
    "master": {
        "description": "Coordinates tasks and makes high-level decisions",
        "default_model": "openai/gpt-4o",
        "capabilities": ["planning", "coordination", "decision_making"]
    },
    "brainstorming": {
        "description": "Generates creative ideas and explores approaches",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "capabilities": ["ideation", "analysis", "exploration"]
    },
    "executor": {
        "description": "Executes code and performs file operations",
        "default_model": "moonshot/kimi-k2.5",
        "capabilities": ["code_execution", "file_operations", "tool_usage"]
    },
    "verifier": {
        "description": "Reviews code and validates results",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "capabilities": ["code_review", "testing", "validation"]
    }
}
```

**Configuration** (in `config.yaml`):
```yaml
multi_agent:
  enabled: false  # User can toggle
  roles:
    master:
      model: openai/gpt-4o
      count: 1
    brainstorming:
      model: anthropic/claude-3-5-sonnet-20241022
      count: 1
    executor:
      model: moonshot/kimi-k2.5
      count: 2  # Can have multiple executors
    verifier:
      model: anthropic/claude-3-5-sonnet-20241022
      count: 1
```

**RoleManager Methods**:
- `assign_role(agent_id, role)`
- `get_role_config(role) -> RoleConfig`
- `spawn_agent_for_role(role) -> agent_id`
- `get_agents_by_role(role) -> List[agent_id]`

### 4. Task Coordination & Result Aggregation

**Purpose**: Distribute tasks to appropriate agents and collect results

**Location**: `kabot/agent/coordinator.py`

**Workflow**:
1. Master agent receives user request
2. Master analyzes task and determines which roles needed
3. Master delegates subtasks to role-specific agents
4. Agents execute in parallel and report back
5. Master aggregates results and responds to user

**Coordinator Methods**:
- `delegate_task(task, target_role) -> task_id`
- `collect_results(task_id) -> List[AgentResult]`
- `aggregate_results(results) -> FinalResult`
- `resolve_conflicts(results) -> ResolvedResult`

**Example Flow**:
```
User: "Implement user authentication"
  ↓
Master Agent (GPT-4o):
  - Analyzes request
  - Delegates to Brainstorming Agent: "Design auth approaches"
  ↓
Brainstorming Agent (Claude Sonnet):
  - Proposes 3 approaches
  - Returns design options
  ↓
Master Agent:
  - Selects approach
  - Delegates to Executor Agent: "Implement JWT auth"
  ↓
Executor Agent (Kimi):
  - Writes code
  - Runs tests
  - Returns implementation
  ↓
Master Agent:
  - Delegates to Verifier Agent: "Review auth implementation"
  ↓
Verifier Agent (Claude Sonnet):
  - Reviews code
  - Checks security
  - Returns feedback
  ↓
Master Agent:
  - Aggregates all results
  - Responds to user
```

### 5. Multi-Bot Support

**Purpose**: Run multiple bot instances on one server sharing agent pool

**Location**: `kabot/bot/bot_registry.py`

**Bot Registry Structure**:
```python
{
    "bots": {
        "telegram:123456": {
            "bot_id": "telegram:123456",
            "platform": "telegram",
            "chat_id": "123456",
            "assigned_agent": "agent-uuid-1",
            "mode": "multi",  # single or multi
            "created_at": "2026-02-18T10:00:00Z"
        },
        "discord:789012": {
            "bot_id": "discord:789012",
            "platform": "discord",
            "chat_id": "789012",
            "assigned_agent": "agent-uuid-1",
            "mode": "single",
            "created_at": "2026-02-18T10:01:00Z"
        }
    }
}
```

**Persistence**: `~/.kabot/bots/registry.json`

**BotRegistry Methods**:
- `register_bot(platform, chat_id, mode) -> bot_id`
- `get_bot(bot_id) -> BotInfo`
- `assign_agent(bot_id, agent_id)`
- `get_bots_for_agent(agent_id) -> List[BotInfo]`
- `update_mode(bot_id, mode)`

**Shared Agent Pool**:
- One master agent can serve multiple bots
- Each bot maintains separate session
- Agent responses routed to correct bot via bot_id

### 6. Mode Selection (Single vs Multi-Agent)

**Purpose**: Let users choose execution mode

**Location**: `kabot/agent/mode_manager.py`

**User Commands**:
- `/mode single` - Use single agent (current behavior)
- `/mode multi` - Use multi-agent orchestration
- `/mode status` - Show current mode and active agents
- `/mode config` - Configure custom multi-agent setup

**Mode Configuration** (per user):
```python
{
    "user:telegram:123456": {
        "mode": "multi",
        "custom_config": {
            "master": "openai/gpt-4o",
            "brainstorming": "anthropic/claude-3-5-sonnet-20241022",
            "executor": "moonshot/kimi-k2.5",
            "verifier": "anthropic/claude-3-5-sonnet-20241022"
        }
    }
}
```

**Persistence**: `~/.kabot/users/mode_config.json`

**ModeManager Methods**:
- `set_mode(user_id, mode)`
- `get_mode(user_id) -> str`
- `set_custom_config(user_id, config)`
- `get_custom_config(user_id) -> dict`

## Implementation Strategy

### Phase 1: Foundation (Tasks #3, #4)
1. Implement AgentRegistry with persistence
2. Implement AgentComm protocol
3. Extend MessageBus with agent_messages queue
4. Write tests for registry and communication

### Phase 2: Role System (Task #5)
1. Implement RoleManager with role definitions
2. Add role-based model assignment
3. Update config.yaml schema
4. Write tests for role assignment

### Phase 3: Coordination (Task #6)
1. Implement Coordinator for task delegation
2. Implement result aggregation logic
3. Implement conflict resolution
4. Write tests for coordination

### Phase 4: Multi-Bot (Task #7)
1. Implement BotRegistry
2. Update channel handlers to use bot_id
3. Implement agent-bot assignment
4. Write tests for multi-bot scenarios

### Phase 5: Mode Selection (Task #8)
1. Implement ModeManager
2. Add /mode commands
3. Update AgentLoop to check mode
4. Write tests for mode switching

### Phase 6: Integration & Testing (Task #9)
1. Integration tests for full workflow
2. Performance tests with multiple agents
3. Stress tests with multiple bots
4. Documentation and examples

## File Structure

```
kabot/
├── agent/
│   ├── agent_registry.py       # NEW: Agent tracking
│   ├── agent_comm.py           # NEW: Agent-to-agent communication
│   ├── role_manager.py         # NEW: Role-based assignment
│   ├── coordinator.py          # NEW: Task coordination
│   ├── mode_manager.py         # NEW: Mode selection
│   └── loop.py                 # MODIFIED: Check mode, route to coordinator
├── bot/
│   └── bot_registry.py         # NEW: Multi-bot tracking
├── bus/
│   └── queue.py                # MODIFIED: Add agent_messages queue
└── config/
    └── schema.py               # MODIFIED: Add multi_agent config

tests/
├── agent/
│   ├── test_agent_registry.py
│   ├── test_agent_comm.py
│   ├── test_role_manager.py
│   ├── test_coordinator.py
│   └── test_mode_manager.py
├── bot/
│   └── test_bot_registry.py
└── integration/
    └── test_multi_agent_workflow.py
```

## Security Considerations

1. **Agent Isolation**: Each agent has separate session and memory
2. **Message Validation**: Validate all agent messages for tampering
3. **Rate Limiting**: Prevent agent message flooding
4. **Access Control**: Agents can only access their assigned resources
5. **Audit Trail**: Log all agent-to-agent communications

## Performance Considerations

1. **Parallel Execution**: Agents run in parallel via asyncio
2. **Message Queue**: Use asyncio.Queue for non-blocking communication
3. **Connection Pooling**: Reuse LLM provider connections
4. **Caching**: Cache role configs and agent info
5. **Cleanup**: Periodic cleanup of inactive agents

## Backward Compatibility

- Default mode is `single` (current behavior)
- Existing code works without changes
- Multi-agent is opt-in via `/mode multi`
- Config migration handled automatically

## Success Criteria

1. ✅ Multiple agents can communicate with each other
2. ✅ Role-based model assignment works correctly
3. ✅ Task coordination distributes work appropriately
4. ✅ Multiple bots can share one agent pool
5. ✅ Users can switch between single/multi modes
6. ✅ One model can power multiple agents/bots
7. ✅ All tests pass (unit + integration)
8. ✅ Performance acceptable (< 2x overhead vs single-agent)

## Next Steps

1. Complete this design document
2. Write comprehensive tests (TDD)
3. Implement components in order (Phase 1-6)
4. Integration testing
5. Documentation and examples
