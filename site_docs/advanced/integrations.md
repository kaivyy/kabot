# Integrations and Extensions

Kabot has two broad extension paths.

## Path 1: Native Product Surfaces

These are built-in product areas such as:
- gateway
- dashboard
- channels
- native Google flows
- built-in tools and runtime handlers

Choose this path when you need something that deeply affects:
- routing
- operator UI
- webhook handling
- background runtime behavior

## Path 2: Skills and External Workflows

Choose skills or external capabilities when you need:
- a guided workflow
- a specific API integration
- a task-specific capability that does not require a new core runtime surface

## MCP Sits Between Core And Skills

MCP is not just another skill, and it is not the same as writing a brand-new built-in product surface either.

Use MCP when you need:
- a live external server capability
- tools discovered from that server at runtime
- resources or prompts that belong to that server
- session-scoped attachment instead of global hardcoding

In Kabot `v0.6.3`, MCP is now a grounded runtime capability:
- configured through the typed config surface
- inspectable through `kabot mcp ...`
- attached per session
- exposed only when the server is actually available

## When A Core Code Change Is Actually Needed

A core change is more likely necessary when you need:
- a new webhook listener
- a new long-running service or daemon behavior
- a brand-new dashboard/operator surface
- deep runtime or routing changes

## Examples

### Good Skill Candidate
- new productivity integration with API key auth
- repo helper that uses existing filesystem and shell tools
- workflow assistant for a narrow domain

### Good Core Candidate
- new first-class inbound channel
- new dashboard monitoring family
- new runtime policy layer

## Documentation Advice For Extensions

If you add a major extension path, document all of these:
- setup
- auth
- runtime assumptions
- failure modes
- how to verify it works
