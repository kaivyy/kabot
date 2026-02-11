import yaml
import re
from pathlib import Path

def validate_skill(skill_path: Path) -> list[str]:
    """
    Validate a skill directory structure and content.
    Returns a list of error messages (empty if valid).
    """
    errors = []
    skill_md = skill_path / "SKILL.md"

    if not skill_md.exists():
        return [f"Missing SKILL.md in {skill_path.name}"]

    try:
        content = skill_md.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Rule 1: Conciseness
        if len(lines) > 500:
            errors.append(f"SKILL.md is too long ({len(lines)} lines). Max 500 lines. Move details to references/.")

        # Rule 2: Metadata Frontmatter
        if not content.startswith("---"):
            errors.append("Missing frontmatter metadata (must start with '---')")

        # Rule 3: Check structure
        # (Optional) We could check for 'scripts' or 'references' folders here if needed

    except Exception as e:
        errors.append(f"Error reading SKILL.md: {str(e)}")

    return errors
