# Output Patterns and Templates

Use these templates to keep Kabot skills consistent, compact, and distribution-friendly.

## SKILL.md Template

```markdown
---
name: my-skill
description: "What this skill does and when to use it."
metadata:
  kabot:
    emoji: "🧩"
    description: "Short description of what the skill does."
---

# My Skill

## Overview
Describe the outcome this skill owns and the problem it solves.

## When to Use
- Trigger condition 1
- Trigger condition 2

## When Not to Use
- Avoid condition 1
- Avoid condition 2

## Instructions
1. Clarify only the details that matter.
2. Prefer existing Kabot tools before inventing manual workarounds.
3. Read `references/` only when relevant.
4. Run `scripts/` when deterministic execution helps.

## References
- `references/api.md` for docs, schemas, and examples.

## Scripts
- `scripts/main.py` for deterministic helper logic when needed.

## Assets
- `assets/template.json` for payload samples or output templates.
```

## Script Template (Python)

```python
#!/usr/bin/env python3
"""Deterministic helper for a Kabot skill."""

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Script description")
    parser.add_argument("action", help="Action to perform")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    try:
        result = {"status": "success", "action": args.action}
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

## Packaging Checklist

```text
1. python skills/skill-creator/scripts/quick_validate.py skills/<skill-name>
2. python skills/skill-creator/scripts/package_skill.py skills/<skill-name> dist/
3. Inspect the resulting .skill bundle before sharing it
```
