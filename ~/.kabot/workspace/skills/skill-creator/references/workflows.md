# Skill Creation Workflow

Standard workflow for creating high-quality skills in Kabot.

## Phase 1: Discovery (Interactive — REQUIRED)
- **Goal**: Fully understand the user's need through Q&A.
- **Actions**:
  - ASK user about use case, scope, and expected outcomes.
  - ASK about external APIs, auth methods, and credentials.
  - ASK about dependencies and preferences.
  - Clarify edge cases and limitations.
  - DO NOT proceed until all questions are answered.

## Phase 2: Planning (Requires Approval — REQUIRED)
- **Goal**: Create a detailed plan and get user sign-off.
- **Actions**:
  - Write implementation plan covering:
    - Folder structure
    - File list with descriptions
    - API endpoints and auth flow (if applicable)
    - Dependencies
  - Present plan to user and ask for approval.
  - Iterate if user requests changes.

## Phase 3: Execution (After Approval Only)
- **Goal**: Build the skill according to the approved plan.
- **Actions**:
  - Run `init_skill.py` to scaffold the directory structure.
  - Write `SKILL.md` — keep concise (< 100 lines if possible).
  - Implement scripts in `scripts/` with `argparse` CLI interfaces (if needed).
  - Add documentation in `references/` for complex APIs (if needed).
  - Install any required dependencies.

## Phase 4: Verification
- **Goal**: Confirm the skill works and is discoverable.
- **Actions**:
  - Run scripts with `--help` to verify CLI interface.
  - Test core functionality.
  - Confirm `SkillsLoader` detects the new skill.
  - Show results to user.

## Directory Convention

Skills are created in the builtin skills directory:
```
kabot/skills/<skill-name>/
```

The `SkillsLoader` scans this directory automatically.
New skills are immediately available after creation.
