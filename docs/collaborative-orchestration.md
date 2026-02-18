# Collaborative Orchestration

Multiple agents work together on a single task with role-based specialization.

## Roles

- **Master**: Coordinates tasks and makes decisions
- **Brainstorming**: Generates ideas and explores approaches
- **Executor**: Executes code and performs operations
- **Verifier**: Reviews code and validates results

## Usage

Enable collaborative mode:

```bash
kabot mode set multi
```

Check current mode:

```bash
kabot mode status
```

## Example Workflow

```
User: "Implement user authentication"
  ↓
Master Agent: Analyzes request
  ↓
Brainstorming Agent: Proposes 3 approaches
  ↓
Master Agent: Selects JWT approach
  ↓
Executor Agent: Implements code
  ↓
Verifier Agent: Reviews implementation
  ↓
Master Agent: Aggregates results → User
```

## Configuration

Custom role-model assignment in `config.yaml`:

```yaml
collaborative:
  roles:
    master: openai/gpt-4o
    brainstorming: anthropic/claude-3-5-sonnet-20241022
    executor: moonshot/kimi-k2.5
    verifier: anthropic/claude-3-5-sonnet-20241022
```
