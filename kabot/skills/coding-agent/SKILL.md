---
name: coding-agent
description: "Spawn, control, and orchestrate Codex CLI, Claude Code, OpenCode, or Pi Coding Agent as background subprocesses. Use when the user wants to run a coding agent in a project directory, monitor its progress, send input, or manage parallel agent sessions."
metadata:
  {
    "kabot": { "emoji": "🧩", "requires": { "anyBins": ["claude", "codex", "opencode", "pi"] } },
  }
---

# Coding Agent (bash-first)

Use **bash** (with optional background mode) for all coding agent work.

## PTY Mode Required

Coding agents are interactive terminal applications that need a pseudo-terminal. **Always use `pty:true`**:

```bash
# Correct - with PTY
bash pty:true command:"codex exec 'Your prompt'"

# Wrong - no PTY, agent may break
bash command:"codex exec 'Your prompt'"
```

### Bash Tool Parameters

| Parameter    | Type    | Description                                                                 |
| ------------ | ------- | --------------------------------------------------------------------------- |
| `command`    | string  | The shell command to run                                                    |
| `pty`        | boolean | **Required for coding agents.** Allocates a pseudo-terminal                 |
| `workdir`    | string  | Working directory (agent sees only this folder's context)                   |
| `background` | boolean | Run in background, returns sessionId for monitoring                         |
| `timeout`    | number  | Timeout in seconds (kills process on expiry)                                |
| `elevated`   | boolean | Run on host instead of sandbox (if allowed)                                 |

### Process Tool Actions (for background sessions)

| Action      | Description                                          |
| ----------- | ---------------------------------------------------- |
| `list`      | List all running/recent sessions                     |
| `poll`      | Check if session is still running                    |
| `log`       | Get session output (with optional offset/limit)      |
| `write`     | Send raw data to stdin                               |
| `submit`    | Send data + newline (like typing and pressing Enter) |
| `send-keys` | Send key tokens or hex bytes                         |
| `paste`     | Paste text (with optional bracketed mode)            |
| `kill`      | Terminate the session                                |

## Workflow

### One-Shot Tasks

```bash
# Quick chat (Codex needs a git repo)
SCRATCH=$(mktemp -d) && cd $SCRATCH && git init && codex exec "Your prompt here"

# In a real project - with PTY
bash pty:true workdir:~/Projects/myproject command:"codex exec 'Add error handling to the API calls'"
```

### Background Tasks (long-running)

```bash
# 1. Start agent in target directory
bash pty:true workdir:~/project background:true command:"codex exec --full-auto 'Build a snake game'"
# Returns sessionId for tracking

# 2. Monitor progress
process action:log sessionId:XXX

# 3. Check if done
process action:poll sessionId:XXX

# 4. Send input if needed
process action:submit sessionId:XXX data:"yes"

# 5. Kill if needed
process action:kill sessionId:XXX
```

### Parallel Issue Fixing with git worktrees

```bash
# 1. Create worktrees for each issue
git worktree add -b fix/issue-78 /tmp/issue-78 main
git worktree add -b fix/issue-99 /tmp/issue-99 main

# 2. Launch agents in each (background + PTY)
bash pty:true workdir:/tmp/issue-78 background:true command:"pnpm install && codex --yolo 'Fix issue #78: <description>. Commit and push.'"
bash pty:true workdir:/tmp/issue-99 background:true command:"pnpm install && codex --yolo 'Fix issue #99: <description>. Commit and push.'"

# 3. Monitor and create PRs after fixes
process action:list
```

## Agent-Specific Notes

### Codex CLI

- Default model: `gpt-5.2-codex`
- `exec "prompt"`: one-shot, exits when done
- `--full-auto`: sandboxed, auto-approves in workspace
- `--yolo`: no sandbox, no approvals (fastest, most dangerous)
- Requires a git repo — use `mktemp -d && git init` for scratch work
- Never review PRs in Kabot's own project folder — clone to temp or use git worktree

### Claude Code

```bash
bash pty:true workdir:~/project command:"claude 'Your task'"
```

### OpenCode

```bash
bash pty:true workdir:~/project command:"opencode run 'Your task'"
```

### Pi Coding Agent

```bash
bash pty:true workdir:~/project command:"pi 'Your task'"
# Non-interactive: pi -p 'Summarize src/'
# Different provider: pi --provider openai --model gpt-4o-mini -p 'Your task'
```

## Rules

1. **Always use pty:true** — coding agents need a terminal.
2. **Respect tool choice** — if user asks for Codex, use Codex. Do not silently take over if an agent fails; respawn or ask.
3. **Be patient** — do not kill sessions prematurely.
4. **Monitor with process:log** — check progress without interfering.
5. **Never start Codex in the Kabot project directory** — use a separate working directory.

## Progress Updates

When spawning coding agents in the background:
- Send 1 short message when starting (what + where).
- Update only on milestones, errors, agent questions, or completion.
- If killing a session, explain why immediately.

## Auto-Notify on Completion

Append a wake trigger to long-running prompts:

```bash
bash pty:true workdir:~/project background:true command:"codex --yolo exec 'Build a REST API for todos.

When completely finished, run: kabot system event --text \"Done: Built todos REST API\" --mode now'"
```
