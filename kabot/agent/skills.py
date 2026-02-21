"""Skills loader for agent capabilities."""

import json
import logging
import os
import re
import shutil
from pathlib import Path

from kabot.utils.skill_validator import validate_skill

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"

logger = logging.getLogger(__name__)

# Workflow chains: when skill X matches, also suggest related skills
WORKFLOW_CHAINS: dict[str, list[str]] = {
    "brainstorming": ["writing-plans", "executing-plans"],
    "writing-plans": ["executing-plans"],
    "systematic-debugging": ["test-driven-development"],
    "executing-plans": ["finishing-a-development-branch"],
    "requesting-code-review": ["finishing-a-development-branch"],
}

# Stop words to ignore when matching (multilingual)
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "or", "and", "not", "no", "it", "its", "this", "that",
    "use", "using", "when", "you", "your", "via", "can", "do",
    "tool", "tools", "skill", "skills",
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "untuk",
    "pakai", "pake", "pakaiin",
})


def _naive_stem(word: str) -> str:
    """Very basic suffix stripping for keyword matching.
    
    Not a real stemmer — just enough to match 'debugging'→'debug',
    'plans'→'plan', 'writing'→'write', etc.
    """
    if len(word) <= 4:
        return word
    for suffix in ("ation", "tion", "ment", "ness", "ity", "ing", "ies", "ed", "ly", "es", "er", "al", "ful"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[:-len(suffix)]
            # Handle doubled consonant: debugging→debugg→debug, running→runn→run
            if len(stem) >= 4 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                stem = stem[:-1]
            # Handle silent 'e' restoration after -ing: writing→writ→write, creating→creat→create
            if suffix == "ing" and len(stem) >= 3 and stem[-1] in "tdkcvz":
                stem += "e"
            return stem
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, filtering stop words + stemming."""
    words = re.findall(r'[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u3000-\u9FFF\uAC00-\uD7AF]{2,}', text.lower())
    stemmed = {_naive_stem(w) for w in words if w not in _STOP_WORDS}
    # Also keep original words (so "debug" matches "debug" directly)
    originals = {w for w in words if w not in _STOP_WORDS}
    return stemmed | originals



class SkillsLoader:
    """
    Loader for agent skills.
    
    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.
    """
    
    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self._skill_index: dict[str, set[str]] | None = None  # lazy cache
        self._body_index: dict[str, set[str]] | None = None   # lazy cache

    def _build_skill_index(self) -> dict[str, set[str]]:
        """Build keyword index from all skill descriptions (cached)."""
        if self._skill_index is not None:
            return self._skill_index

        index: dict[str, set[str]] = {}
        body_index: dict[str, set[str]] = {}
        for skill in self.list_skills(filter_unavailable=False):
            desc = self._get_skill_description(skill["name"])
            # Primary keywords: from description + skill name (high signal)
            keywords = _extract_keywords(desc)
            keywords.update(_extract_keywords(skill["name"].replace("-", " ").replace("_", " ")))
            index[skill["name"]] = keywords
            # Secondary keywords: from body content (lower signal, more noise)
            content = self.load_skill(skill["name"])
            if content:
                body = self._strip_frontmatter(content)[:500]
                body_kw = _extract_keywords(body)
                body_index[skill["name"]] = {kw for kw in body_kw if len(kw) >= 4} - keywords
            else:
                body_index[skill["name"]] = set()

        self._skill_index = index
        self._body_index = body_index
        return index

    def match_skills(self, message: str, profile: str = "GENERAL",
                     max_results: int = 3) -> list[str]:
        """
        Auto-select relevant skills based on user message content.

        Scores each skill by keyword overlap between the message and the
        skill's description. Applies workflow chain expansion for related skills.

        Args:
            message: User message text.
            profile: Router profile (CODING, CHAT, RESEARCH, GENERAL).
            max_results: Maximum number of skills to return.

        Returns:
            List of skill names, sorted by relevance score (best first).
        """
        if not message or len(message.strip()) < 5:
            return []

        index = self._build_skill_index()
        msg_keywords = _extract_keywords(message)

        if not msg_keywords:
            return []

        # Score each skill
        body_idx = self._body_index or {}
        scored: list[tuple[str, float]] = []
        for skill_name, skill_keywords in index.items():
            if not skill_keywords:
                continue

            # Primary overlap: description + name keywords (high signal)
            overlap = msg_keywords & skill_keywords
            # Secondary overlap: body keywords (low signal)
            body_overlap = msg_keywords & body_idx.get(skill_name, set())
            
            if not overlap and not body_overlap:
                continue

            # Primary keywords score 1.0 each, body keywords 0.2 each
            score = len(overlap) + 0.2 * len(body_overlap)

            # Strong bonus: exact skill name match (e.g., user says "spotify" or "discord")
            name_words = set(skill_name.replace("-", " ").split())
            # Also check stemmed name words (e.g., "debugging" → "debug")
            stemmed_name = {_naive_stem(w) for w in name_words}
            stemmed_msg = {_naive_stem(w) for w in msg_keywords}
            name_overlap = (name_words & msg_keywords) | (stemmed_name & stemmed_msg)
            if name_overlap:
                score += 2.0 * len(name_overlap)

            # Bonus for action/domain word overlap (verbs that indicate intent)
            action_words = {"debug", "fix", "error", "bug", "test", "create", "build",
                            "search", "find", "send", "play", "download", "upload",
                            "read", "write", "edit", "delete", "check", "control",
                            "summarize", "transcribe", "generate", "manage", "schedule",
                            "deploy", "install", "configure", "monitor", "order", "capture"}
            all_overlap = overlap | body_overlap
            action_overlap = all_overlap & action_words
            if action_overlap:
                score += 0.3 * len(action_overlap)

            # Skip weak matches: require 2+ overlaps unless name matches
            if not name_overlap and len(overlap) + len(body_overlap) < 2:
                continue

            scored.append((skill_name, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top N
        selected = [name for name, _ in scored[:max_results]]

        # Expand workflow chains
        expanded: list[str] = []
        for skill_name in selected:
            if skill_name not in expanded:
                expanded.append(skill_name)
            for chain_skill in WORKFLOW_CHAINS.get(skill_name, []):
                if chain_skill not in expanded and len(expanded) < max_results + 2:
                    expanded.append(chain_skill)

        # Validate requirements for selected skills
        validated = []
        for skill_name in expanded:
            meta = self._get_skill_meta(skill_name)
            if self._check_requirements(meta):
                validated.append(skill_name)
            else:
                missing = self._get_missing_requirements(meta)
                install_info = meta.get("install", {})
                install_cmd = install_info.get("cmd", "")
                hint = f"[SKILL_UNAVAILABLE] {skill_name} needs: {missing}"
                if install_cmd:
                    hint += f" (install: {install_cmd})"
                from loguru import logger
                logger.info(hint)
                # Still include the skill name but mark it
                validated.append(f"{skill_name} [NEEDS: {missing}]")

        return validated[:max_results + 2]  # Allow up to 5 with chains
    
    def list_skills(self, filter_unavailable: bool = True) -> list[dict]:
        """
        List all available skills with detailed status.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts with 'name', 'path', 'source', 'valid',
            'eligible', 'missing' (bins, env), 'install', 'description'.
        """
        skills = []
        seen_names = set()

        def _process_skill(name, path, source, valid):
            if name in seen_names: return
            seen_names.add(name)

            meta = self._get_skill_meta(name)
            desc = self._get_skill_description(name)
            
            # Check requirements
            missing_bins = []
            missing_env = []
            requires = meta.get("requires", {})
            
            for b in requires.get("bins", []):
                if not shutil.which(b):
                    missing_bins.append(b)
            
            for e in requires.get("env", []):
                if not os.environ.get(e):
                    missing_env.append(e)

            # Check OS (simple check against platform)
            unsupported_os = []
            if requires.get("os"):
                import sys
                required_os = requires["os"]
                current_os = sys.platform
                if isinstance(required_os, list):
                    if current_os not in required_os and ("win32" not in required_os or current_os != "win32"):
                         # Basic mapping: win32=windows, darwin=macos, linux=linux
                         # But let's assume 'os' field matches sys.platform values or common names
                         pass # TODO: Better OS matching
                elif required_os != current_os:
                     unsupported_os.append(required_os)

            eligible = len(missing_bins) == 0 and len(missing_env) == 0 and len(unsupported_os) == 0
            
            # primaryEnv logic: explicit meta > first missing env > first required env
            primary_env = meta.get("primaryEnv")
            if not primary_env and missing_env:
                primary_env = missing_env[0]
            if not primary_env and requires.get("env"):
                 primary_env = requires.get("env")[0]

            skill_info = {
                "name": name,
                "path": str(path),
                "source": source,
                "valid": valid,
                "eligible": eligible,
                "primaryEnv": primary_env,
                "missing": {
                    "bins": missing_bins,
                    "env": missing_env,
                    "os": unsupported_os
                },
                "install": meta.get("install", {}), # e.g. {"cmd": "pip install ..."}
                "description": desc
            }
            skills.append(skill_info)

        # Workspace skills (highest priority)
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "workspace", len(errors) == 0)

        # Built-in skills
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        errors = validate_skill(skill_dir)
                        _process_skill(skill_dir.name, skill_file, "builtin", len(errors) == 0)

        # Filter by requirements
        if filter_unavailable:
            return [s for s in skills if s["eligible"]]
        return skills
    
    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.
        
        Args:
            name: Skill name (directory name).
        
        Returns:
            Skill content or None if not found.
        """
        # Check workspace first
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")
        
        # Check built-in
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")
        
        return None
    
    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.
        
        Args:
            skill_names: List of skill names to load.
        
        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        
        return "\n\n---\n\n".join(parts) if parts else ""
    
    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).
        
        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.
        
        Returns:
            XML-formatted skills summary.
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""
        
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(self._get_skill_description(s["name"]))
            skill_meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)
            
            lines.append(f"  <skill available=\"{str(available).lower()}\">")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")
            
            # Show missing requirements for unavailable skills
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")
            
            lines.append(f"  </skill>")
        lines.append("</skills>")
        
        return "\n".join(lines)
    
    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """Get a description of missing requirements."""
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)
    
    def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name
    
    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content
    
    def _parse_kabot_metadata(self, raw: str | dict) -> dict:
        """Parse kabot metadata JSON from frontmatter."""
        if isinstance(raw, dict):
            return raw.get("kabot", {})
        try:
            data = json.loads(raw)
            return data.get("kabot", {}) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars)."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True
    
    def _get_skill_meta(self, name: str) -> dict:
        """Get kabot metadata for a skill (cached in frontmatter)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_kabot_metadata(meta.get("metadata", ""))
    
    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_kabot_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result
    
    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.
        
        Args:
            name: Skill name.
        
        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None
        
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                yaml_text = match.group(1)
                try:
                    import yaml
                    return yaml.safe_load(yaml_text) or {}
                except ImportError:
                    # Fallback if PyYAML somehow isn't installed
                    metadata = {}
                    for line in yaml_text.split("\n"):
                        if ":" in line and not line.strip().startswith("{") and not line.strip().startswith("}"):
                            # Very basic single-line parse fallback
                            key, value = line.split(":", 1)
                            metadata[key.strip()] = value.strip().strip('"\'')
                    return metadata
                except Exception:
                    return {}
        
        return None
