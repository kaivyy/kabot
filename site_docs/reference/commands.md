# Commands Reference

This is a practical command map, not a full generated API reference.

## Core Commands

```bash
kabot config
kabot gateway
kabot agent
kabot doctor
```

## Config And Setup

```bash
kabot config
kabot config --token-mode boros
kabot config --token-mode hemat
kabot config --token-saver
kabot config --no-token-saver
```

## Gateway

```bash
kabot gateway
kabot gateway --port 18790
```

## Agent

```bash
kabot agent -m "Hello Kabot"
kabot agent
```

## Doctor

```bash
kabot doctor --fix
kabot doctor routing
kabot doctor smoke-agent --smoke-timeout 30
kabot doctor smoke-agent --smoke-mcp-local-echo
```

## Auth

```bash
kabot auth status
kabot auth login openai
kabot auth login google --method oauth
```

## Agents

```bash
kabot agents list
kabot agents add work --name "Work Agent" --model openai/gpt-4o
kabot agents delete work
```

## MCP

```bash
kabot mcp status
kabot mcp example-config
kabot mcp inspect local_echo
```

## Docs Build

```bash
pip install ".[docs]"
mkdocs serve
mkdocs build --strict
```
