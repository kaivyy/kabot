# Multi-Agent System

Kabot supports multiple independent agents with separate contexts, models, and workspaces. This allows you to run different AI agents for different purposes or channels, each with isolated configuration and session history.

## Overview

The multi-agent system enables:
- Multiple agents with different AI models
- Isolated workspaces and session histories
- Channel-based routing to specific agents
- Default agent fallback for unmatched messages

## Configuration

Add agents to `config.yaml`:

```yaml
agents:
  list:
    - id: work
      name: Work Agent
      model: openai/gpt-4o
      workspace: ~/.kabot/workspace-work
      default: false

    - id: personal
      name: Personal Agent
      model: anthropic/claude-sonnet-4-5
      workspace: ~/.kabot/workspace-personal
      default: true
```

### Agent Properties

- `id`: Unique identifier for the agent (required)
- `name`: Human-readable name (required)
- `model`: AI model to use (required)
- `workspace`: Directory for agent's session data (required)
- `default`: Whether this is the default agent (optional, default: false)

### Channel Bindings

Route specific channels to agents:

```yaml
agents:
  bindings:
    - agent_id: work
      channel: telegram

    - agent_id: personal
      channel: whatsapp
```

Bindings can be:
- Channel-only: Routes all messages from a channel to an agent
- Channel + chat_id: Routes specific chats to an agent (future enhancement)

## CLI Commands

### List Agents

```bash
kabot agents list
```

Shows all configured agents with their properties.

### Add Agent

```bash
kabot agents add work --name "Work Agent" --model openai/gpt-4o
```

Creates a new agent with the specified configuration.

### Delete Agent

```bash
kabot agents delete work
```

Removes an agent from the configuration.

## Message Routing

Messages are routed to agents using this priority:

1. **Exact match**: Channel + chat_id binding (if configured)
2. **Channel match**: Channel-only binding
3. **Default agent**: Fallback if no bindings match

### Routing Examples

With this configuration:

```yaml
agents:
  list:
    - id: work
      name: Work Agent
      default: false
    - id: personal
      name: Personal Agent
      default: true
  bindings:
    - agent_id: work
      channel: telegram
```

- Telegram messages → `work` agent
- WhatsApp messages → `personal` agent (default)
- Any other channel → `personal` agent (default)

## Session Isolation

Each agent maintains complete isolation:

### Workspace Directory
- Separate directory per agent
- Contains session history and state
- Configured via `workspace` property

### Session History
- Independent conversation history
- No cross-agent context sharing
- Persisted in agent's workspace

### Model Configuration
- Each agent uses its own model
- Different models can have different capabilities
- Model settings are per-agent

## Best Practices

### Agent Organization
- Use descriptive agent IDs and names
- Create agents for different contexts (work, personal, testing)
- Set one agent as default for unmatched messages

### Workspace Management
- Use separate workspace directories
- Ensure workspace paths are writable
- Back up workspaces to preserve history

### Channel Bindings
- Bind channels to appropriate agents
- Use default agent as catch-all
- Review bindings when adding new channels

## Troubleshooting

### Agent Not Found
- Verify agent ID exists in `config.yaml`
- Check for typos in agent_id references
- Run `kabot agents list` to see all agents

### Messages Going to Wrong Agent
- Review routing priority (exact → channel → default)
- Check bindings in `config.yaml`
- Ensure default agent is configured

### Workspace Errors
- Verify workspace directory exists and is writable
- Check file permissions
- Ensure sufficient disk space
