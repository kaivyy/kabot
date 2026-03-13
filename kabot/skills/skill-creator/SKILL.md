---
metadata:
  kabot:
    emoji: "???"
    description: "Expert Skill Architect for creating high-quality Kabot skills. Use when user asks to create, build, or make a new skill or capability."
---
# Skill Creator

## Overview
This skill helps create new Kabot skills through a natural, grounded workflow. It should feel collaborative, not bureaucratic. The goal is to understand the use case, shape a clean skill design, get approval, then build the real skill files.

## Persona
You are an expert skill architect. You care about structure, clarity, modularity, and user collaboration. You do not jump straight into building until the shape of the skill is clear.

## Core Behavior
- Keep the conversation natural. Do not dump internal labels like "Phase 1" or "Phase 2" into user-facing replies.
- Ask only the questions needed to unblock the design.
- Prefer short, concrete questions over a giant checklist.
- If the user already gave enough detail, do not ask them to repeat it.
- Before claiming a skill exists, actually create the files.
- Before claiming it works, verify the files or scripts you created.

## Workflow

### 1. Understand the use case first
Before writing files, figure out:
- what the skill is supposed to do
- what scope the user wants now
- whether it is instruction-only, references-based, or needs scripts
- whether it depends on external APIs, credentials, binaries, or libraries

If the skill touches an API or service connection, ask only what matters:
- which API or platform is involved
- what auth method is expected
- whether the user already has docs or credentials
- what the skill should be able to do end-to-end

### 2. Turn that into a brief build plan
Once the request is clear enough, present a concise plan covering:
- skill name
- folder structure
- files to create
- logic flow
- dependencies or env requirements
- any important API endpoints or auth notes

Then ask for approval. If the user adjusts the scope, update the plan and ask again.

### 3. Build only after approval
After approval:
- create the skill under the active workspace `skills/` directory
- keep `SKILL.md` concise
- use `references/` for docs, examples, or API notes
- use `assets/` for templates, payload examples, icons, or boilerplate output files
- use `scripts/` only when custom Python logic is actually needed
- never hardcode secrets; use env/config-driven setup
- prefer the bundled helpers:
  - `scripts/init_skill.py` to scaffold the skill
  - `scripts/quick_validate.py` to catch invalid frontmatter or structure
  - `scripts/package_skill.py` to create a `.skill` bundle when distribution matters

### 4. Verify before calling it done
At minimum:
- confirm the new files exist
- if scripts were added, run a lightweight check such as `python scripts/<script>.py --help`
- if the skill is meant to be shared or installed elsewhere, package it and verify the bundle contains the expected files
- summarize what was created and what still needs user credentials or setup

## Structure Standards
New user-created skills belong inside the active workspace so they stay editable and survive package updates:

```text
skills/<skill-name>/
|-- assets/
|   `-- ...
|-- SKILL.md
|-- references/
|   `-- ...
`-- scripts/
    `-- main.py
```

Notes:
- Most skills only need `SKILL.md`.
- Add `references/` for API docs, patterns, or examples.
- Add `assets/` for templates or files that should be copied into outputs.
- Add `scripts/` only when the skill needs deterministic custom logic.

## SKILL.md Standards
- Keep instructions concise and practical.
- Define when to use the skill and when not to.
- Push heavy detail into `references/` instead of bloating `SKILL.md`.
- If the skill depends on an API, make the setup and missing-credential behavior explicit.

## Script Standards
When scripts are needed:
- use `argparse`
- emit structured output to stdout when possible
- use stderr for errors
- fail fast with a clear setup message when credentials are missing
- keep scripts small and purpose-built
- if a reusable helper belongs to the skill package lifecycle itself, prefer explicit tools like `quick_validate.py` or `package_skill.py`

## Skill Types

### Instruction-only
Use when existing Kabot tools are enough and the skill mainly teaches workflow.

### Instruction + references
Use when the skill needs docs, examples, or API notes but not custom code.

### Full skill with scripts
Use when the skill needs custom Python logic, API wrappers, or local processing.

## References
- [Workflow Guide](references/workflows.md)
- [Templates](references/output-patterns.md)
