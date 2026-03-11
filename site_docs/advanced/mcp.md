# MCP Runtime

Kabot `v0.6.3` includes a Python-native MCP runtime.

That matters because MCP is now a real runtime surface, not only a prompt convention.

## What Kabot Supports

Kabot can:

- attach configured MCP servers to a session
- list real MCP tools
- inspect MCP resources
- inspect MCP prompts
- expose MCP tools with namespaced names such as `mcp.local_echo.echo`
- keep MCP follow-up continuity grounded to the current session

Kabot currently supports these transports:

- `stdio`
- `streamable_http`

## Quick Commands

```bash
kabot mcp status
kabot mcp example-config
kabot mcp inspect local_echo
```

## Minimal Config Example

```json
{
  "mcp": {
    "enabled": true,
    "servers": {
      "local_echo": {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "kabot.mcp.dev.echo_server"]
      },
      "remote_docs": {
        "transport": "streamable_http",
        "url": "https://example.test/mcp"
      }
    }
  }
}
```

## Why This Is Safer

The runtime now follows a stricter model:

- if an MCP server is configured and attached, Kabot can expose its real capabilities
- if an MCP server is missing or unavailable, Kabot should say so directly
- MCP prompt/resource references can be pulled into turn context without pretending they are ordinary files
- continuity is stronger, but a newer explicit user request can still override stale MCP context

## MCP Versus Skills

Use MCP when you want:

- a live external server capability
- tools discovered from that server at runtime
- resources or prompts that belong to that server
- session-scoped attachment instead of global hardcoding

Use Skills when you want:

- workflow guidance
- setup guidance
- domain-specific operating procedures
- tool selection discipline rather than a new runtime transport

## Verification Workflow

Good operator workflow:

1. configure one MCP server
2. run `kabot mcp status`
3. run `kabot mcp inspect <server>`
4. run one narrow real prompt
5. only then add more MCP servers

This keeps the runtime honest and easier to debug.
