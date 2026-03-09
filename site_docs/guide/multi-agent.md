# Multi-Agent Guide

Kabot can run multiple agents with separate workspaces, models, and routing rules.

## Why Use Multiple Agents

Use multiple agents when one bot should not do everything.

Examples:
- work agent
- personal agent
- support agent
- research agent
- automation agent

## What Stays Separate Per Agent

- workspace
- session history
- model path
- bindings and usage context

## Simple Example

```yaml
agents:
  list:
    - id: work
      name: Work Agent
      model: openai/gpt-4o
      workspace: ~/.kabot/workspace-work
    - id: personal
      name: Personal Agent
      model: anthropic/claude-sonnet-4-5
      workspace: ~/.kabot/workspace-personal
      default: true
```

## Routing Basics

Messages generally resolve by:
1. exact binding
2. channel binding
3. default agent fallback

## Best Practices

- give each agent a clear role
- keep one default agent
- use separate workspaces
- avoid overloading one agent with every channel and every task

## When Multi-Agent Is Worth It

Choose multi-agent when:
- different channels need different models
- different users need different personas or boundaries
- you want cleaner memory separation
- you need dedicated role-based automation
