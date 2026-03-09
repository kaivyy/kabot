# Operator Patterns

This page describes practical ways to run Kabot well over time.

## Pattern 1: One Stable Test Prompt Set

Keep a small set of known-good prompts for:
- temporal response
- filesystem navigation
- model override
- dashboard chat
- one inbound channel message

Run them after meaningful config or runtime changes.

## Pattern 2: Separate Observation From Mutation

In the dashboard and gateway world, first observe, then mutate.

Good sequence:
1. open dashboard
2. inspect health, sessions, and nodes
3. confirm scope/auth mode
4. then use write actions

## Pattern 3: One Change At A Time

Do not change:
- model chain
- channel binding
- gateway auth token
- memory mode

all at once.

Change one thing, smoke test, then continue.

## Pattern 4: Scope-Aware Tokens

Use:
- `operator.read` for observation-only operators
- `operator.write` only where mutation is necessary
- `ingress.write` only where webhook ingestion is needed

## Pattern 5: Role-Based Agents

Use multiple agents when roles genuinely differ.

Examples:
- support agent for customer-facing channels
- research agent for long-form exploratory tasks
- work agent for coding and operations

## Pattern 6: Treat Skills As Capabilities, Not Magic

A skill still needs:
- relevant env keys
- any required binaries
- a good runtime path
- realistic operator expectations

## Pattern 7: Use Doctor And Smoke Checks Proactively

Operator confidence comes from repeatable checks, not intuition.

```bash
kabot doctor --fix
kabot doctor smoke-agent --smoke-timeout 30
```
