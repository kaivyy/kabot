# CLI Guide

The CLI is the fastest way to test Kabot and the most direct way to operate it from a terminal.

## Most Important Commands

```bash
kabot config
kabot gateway
kabot agent -m "Hello Kabot"
kabot doctor --fix
```

## One-Shot Prompts

```bash
kabot agent -m "Summarize today's priorities"
```

Use one-shot mode when you want:
- fast testing
- scripting
- automation hooks
- smoke checks

## Interactive Mode

```bash
kabot agent
```

Use interactive mode when you want:
- a longer conversation
- follow-up context inside the same session
- repeated manual testing

## Health And Diagnostics

```bash
kabot doctor --fix
kabot doctor routing
kabot doctor smoke-agent --smoke-timeout 30
```

These help when:
- startup feels wrong
- routing seems inconsistent
- you want a quick agent verification loop

## Auth And Model Management

Common patterns include:

```bash
kabot auth status
kabot auth login openai
kabot auth login google --method oauth
```

## Agent And Multi-Agent Management

```bash
kabot agents list
kabot agents add work --name "Work Agent" --model openai/gpt-4o
```

## Good CLI Habits

- use one-shot prompts for reproducible checks
- use interactive mode for exploratory conversations
- keep a note of your known-good test prompt set
- re-run `doctor smoke-agent` after risky runtime changes

## Advanced CLI Note

Recent Kabot improvements make one-shot runs safer by isolating ad-hoc prompts from stale default session context when no explicit session is provided.
