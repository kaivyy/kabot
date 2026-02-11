# Output Patterns and Templates

Use these templates to ensure consistency across Kabot skills.

## SKILL.md Template

```markdown
---
metadata:
  kabot:
    emoji: 🧩
    description: "Short description of what the skill does."
---
# Skill Name

## Overview
Briefly describe the purpose of this skill and when to use it.

## Persona
Define the specific role the agent should adopt (e.g., "Expert Data Analyst", "Senior Python Developer").

## Goals
1. Primary goal.
2. Secondary goal.

## Instructions
1. **Step 1**: Description of action.
2. **Step 2**: Description of action.
   - Detail: ...
3. **Step 3**: ...

## Commands
- `/command_name`: Description of what this command triggers.

## References
- [Workflow Guide](references/workflows.md)
- [Templates](references/output-patterns.md)
```

## Script Template (Python)

```python
#!/usr/bin/env python3
"""
Description of the script's purpose.
"""
import argparse
import sys
import json

def main():
    parser = argparse.ArgumentParser(description="Script description")
    parser.add_argument("--input", required=True, help="Input argument")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    try:
        # Core logic here
        result = process_data(args.input)

        # Output JSON or text to stdout
        print(json.dumps({"status": "success", "data": result}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}), file=sys.stderr)
        sys.exit(1)

def process_data(input_val):
    # Implementation details
    return f"Processed {input_val}"

if __name__ == "__main__":
    main()
```
