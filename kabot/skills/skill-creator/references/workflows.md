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
  - Create/scaffold the skill inside the active workspace `skills/` directory.
  - Write `SKILL.md` — keep concise (< 100 lines if possible).
  - Implement scripts in `scripts/` with `argparse` CLI interfaces (if needed).
  - Add documentation in `references/` for complex APIs (if needed).
  - For API skills, declare `requires.env` and `primaryEnv`; read secrets from env/config instead of hardcoding them.
  - Install any required dependencies only when needed and approved.

## Phase 4: Verification
- **Goal**: Confirm the skill works and is discoverable.
- **Actions**:
  - Run scripts with `--help` to verify CLI interface.
  - Test core functionality.
  - Confirm `SkillsLoader` detects the new skill.
  - Show results to user.

## Directory Convention

Skills are created in the active workspace skills directory:
```
skills/<skill-name>/
```

The `SkillsLoader` scans workspace skills automatically.
New skills are immediately available after creation.
