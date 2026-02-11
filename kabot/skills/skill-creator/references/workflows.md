# Skill Creation Workflow

This document outlines the standard workflow for creating high-quality skills in Kabot using the Progressive Disclosure pattern.

## Phase 1: Analysis
- **Goal**: Understand the user's need and the problem domain.
- **Actions**:
  - Brainstorm required capabilities.
  - Identify necessary inputs and expected outputs.
  - Determine if external tools or libraries are needed.
  - Define the skill's scope and boundaries.

## Phase 2: Structure
- **Goal**: Set up the file system organization.
- **Actions**:
  - Create a directory for the skill: `kabot/skills/<skill-name>/`.
  - Create standard subdirectories:
    - `scripts/`: For Python logic and complex operations.
    - `references/`: For documentation, templates, and large context files.

## Phase 3: Drafting
- **Goal**: Create the interface and instructions.
- **Actions**:
  - Write `SKILL.md` in the root of the skill directory.
  - Keep `SKILL.md` concise (aim for < 500 lines).
  - Use clear headings and bullet points.
  - Define the persona and high-level goals.
  - Reference detailed documentation in `references/` instead of cluttering the main file.

## Phase 4: Packaging
- **Goal**: Implement robust logic and clean up.
- **Actions**:
  - Move complex logic, data processing, or large prompts into Python scripts in `scripts/`.
  - Ensure scripts use `argparse` for clear CLI interfaces.
  - distinct separation of concerns: `SKILL.md` handles orchestration and LLM interaction, while `scripts/*.py` handle deterministic execution.
