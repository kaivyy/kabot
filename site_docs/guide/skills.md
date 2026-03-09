# Skills Guide

Skills are one of the main ways Kabot becomes more capable without turning into a rigid bot.

## What A Skill Is

A skill is a structured capability package that can teach Kabot how to approach a task or workflow.

Skills can range from:
- planning and debugging workflows
- messaging and channel tasks
- media and integrations
- coding and operational tasks

## The Right Mental Model

A skill is not the same as:
- a plugin
- a model
- a bot persona
- a shell script

A skill is better thought of as a capability contract:
- when it should be used
- how the agent should behave
- what setup is required
- what external tools or APIs it expects

## Types Of Skills

In practice, skills usually fall into one of three buckets:

### 1. Instruction-Only Skills

These mostly steer the agent's behavior and tool usage.

Examples:
- planning workflows
- debugging workflows
- code review workflows

### 2. Integration Skills

These connect Kabot to real external services, often with:
- env keys
- OAuth
- binaries
- API docs

### 3. Workspace Skills

These are custom capabilities created specifically for your own workspace, team, or domain.

## What The Skills Menu Does

In `kabot config`, the `Skills` section is for:
- enabling or disabling skills
- filling in required environment values
- understanding which skills need external setup
- planning dependency installs

## What The Skills Menu Does Not Do

It does not blindly run package-manager installs for everything.

That is intentional.

Kabot separates:
- skill definition discovery
- skill configuration
- dependency planning
- actual tool/runtime installation

That separation is healthy because it prevents:
- accidental installs you did not mean to run
- confusing setup states
- broken assumptions about external runtimes already being available

## Skill Labels You May See

- `needs env`
- `needs binary`
- `needs oauth`
- `needs node package`

These are setup hints, not failures.

## What Those Labels Mean In Practice

| Label | Meaning |
| --- | --- |
| `needs env` | the skill expects env values or API keys |
| `needs binary` | an external executable must exist on the machine |
| `needs oauth` | you must complete an auth/login flow |
| `needs node package` | dependency planning likely touches Node ecosystem tooling |

## Beginner Workflow For Skills

1. start with built-in/native flows first
2. enable only the skills you understand
3. fill required env values
4. read the skill's setup assumptions
5. test one narrow use case

Good beginner question:
- \"Do I need this skill right now, or is native Kabot functionality already enough?\"

## Auto-Selected Skills

Kabot can match relevant skills to a prompt automatically.

Recent runtime improvements keep this more efficient by:
- using faster matching paths for explicit skill requests
- avoiding full skill-catalog bloat on lightweight prompts
- preserving AI-driven responses instead of forcing stiff hardcoded behavior

This matters because the goal is:
- natural conversation first
- deterministic help only where confidence is high
- less prompt bloat
- better runtime speed

## Explicit Skill Requests

You can also ask Kabot to use a skill more directly.

Examples:
- `please use the weather skill for this request`
- `tolong pakai skill weather untuk ini`
- `use the debugging workflow before changing code`

Recent runtime work made these explicit skill turns much lighter, so they no longer need to drag the full skill catalog into the prompt.

## Creating New Skills

Kabot can also help create or install skills through guided conversation.

Good example prompts:
- `create a new skill for Threads posting`
- `install a skill from this GitHub repo`
- `show me installable curated skills`

Expected flow:
1. discovery questions
2. short plan
3. your approval
4. execution

That approval step matters.

Kabot should not jump straight from:
- vague idea
to
- file creation and mutation

without a plan and your go-ahead.

## Installing Third-Party Skills

There is a difference between:
- built-in skills already shipped with Kabot
- workspace skills you create
- external skills pulled from another repo

For external skills, always think about:
- trust
- env requirements
- binaries needed
- who will maintain the dependency later

## Common Mistakes

### Mistake 1: Assuming skill enabled means fully ready

A skill may be enabled but still not operational because:
- env keys are missing
- external CLI is missing
- OAuth is incomplete

### Mistake 2: Treating skills as magic parsers

Skills improve behavior and capability, but they do not remove the need for:
- clear prompts
- proper setup
- correct runtime environment

### Mistake 3: Installing too much too early

Start with a small set of useful skills, not everything.

## Good Skill Strategy

For most users:

### Phase 1
- use native Kabot first
- add only one or two key skills

### Phase 2
- add integration skills that clearly solve a real need

### Phase 3
- create workspace-specific skills for your own workflows

## Related Pages

- [Google Suite guide](google-suite.md)
- [Configuration guide](configuration.md)
- [Advanced integrations](../advanced/integrations.md)

## Best Practices

- enable only what you understand
- fill in env keys before expecting a skill to work fully
- treat third-party installs as real operational dependencies
- keep native built-ins and external skill tooling conceptually separate
