import json
from pathlib import Path
from typing import Any


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


def _manifest_candidates(skill_path: Path) -> list[Path]:
    return [
        skill_path / "SKILL_MANIFEST.json",
        skill_path / "skill-manifest.json",
        skill_path / "manifest.json",
    ]


def _extract_manifest_signer(payload: dict[str, Any]) -> str:
    for key in ("signer", "signed_by", "signedBy", "publisher"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    signature = payload.get("signature")
    if isinstance(signature, dict):
        for key in ("signer", "signed_by", "signedBy"):
            value = signature.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def validate_skill_trust(
    skill_path: Path,
    *,
    verify_skill_manifest: bool,
    allowed_signers: list[str] | None,
) -> tuple[bool, str]:
    """Validate trust-mode manifest signer policy for installed skill."""
    if not verify_skill_manifest:
        return True, "trust manifest verification disabled"

    allowed = {str(v).strip() for v in (allowed_signers or []) if str(v).strip()}
    if not allowed:
        return False, "Trust mode enabled but allowed_signers is empty"

    manifest_path = next((p for p in _manifest_candidates(skill_path) if p.exists()), None)
    if manifest_path is None:
        return False, "Missing skill manifest (SKILL_MANIFEST.json)"

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"Invalid skill manifest JSON: {exc}"

    if not isinstance(payload, dict):
        return False, "Invalid skill manifest: expected JSON object"

    signer = _extract_manifest_signer(payload)
    if not signer:
        return False, "Invalid skill manifest: missing signer"
    if signer not in allowed:
        return False, f"Signer '{signer}' is not trusted"
    return True, f"Trusted signer: {signer}"
