"""SetupWizard section methods: tools_gateway_skills."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.wizard import skills_prompts
from kabot.cli.wizard.ui import ClackUI
from kabot.config.skills_settings import (
    normalize_skills_settings,
    resolve_load_settings,
    resolve_onboarding_settings,
    set_skill_entry_enabled,
    set_skill_entry_env,
)
from kabot.utils.workspace_templates import ensure_workspace_templates

console = Console()

def _resolve_tools_section_override(name: str, fallback):
    try:
        from kabot.cli.wizard.sections import tools_gateway_skills as section_module
    except Exception:
        return fallback
    return getattr(section_module, name, fallback)

def skills_checkbox(*args, **kwargs):
    """Compatibility wrapper so tests can patch either module path."""
    return skills_prompts.skills_checkbox(*args, **kwargs)

def _detect_skill_auth_hint(loader: Any, skill_name: str) -> str | None:
    try:
        content = loader.load_skill(skill_name) or ""
    except Exception:
        return None
    if not content:
        return None

    lowered = content.lower()
    if "oauth" in lowered:
        return "needs oauth"
    auth_patterns = (
        r"\bauth add\b",
        r"\bauth credentials\b",
        r"\bauthenticate\b",
        r"\bsign[\s-]?in\b",
        r"\blog[\s-]?in\b",
        r"\brequires auth\b",
        r"\brequires login\b",
    )
    if any(re.search(pattern, lowered) for pattern in auth_patterns):
        return "needs login"
    return None

def _describe_skill_setup_hint(skill: dict[str, Any], loader: Any) -> str:
    parts: list[str] = []
    missing = skill.get("missing", {}) if isinstance(skill.get("missing"), dict) else {}
    missing_bins = missing.get("bins", []) if isinstance(missing.get("bins"), list) else []
    missing_env = missing.get("env", []) if isinstance(missing.get("env"), list) else []
    install_specs = skill.get("install", []) if isinstance(skill.get("install"), list) else []

    if missing_env:
        parts.append("needs env")

    auth_hint = _detect_skill_auth_hint(loader, str(skill.get("name") or ""))
    if auth_hint:
        parts.append(auth_hint)

    if missing_bins:
        parts.append("needs binary")

    install_kinds = {
        str(spec.get("kind") or "").strip().lower()
        for spec in install_specs
        if isinstance(spec, dict)
    }
    if "node" in install_kinds:
        parts.append("needs node package")
    elif "brew" in install_kinds:
        parts.append("install via brew")
    elif "uv" in install_kinds:
        parts.append("install via uv")
    elif "go" in install_kinds:
        parts.append("install via go")
    elif "download" in install_kinds:
        parts.append("manual download")
    elif install_specs:
        parts.append("has install recipe")

    # Keep ordering stable but avoid duplicate labels.
    seen: set[str] = set()
    deduped = []
    for part in parts:
        if part not in seen:
            deduped.append(part)
            seen.add(part)

    return " | ".join(deduped) if deduped else "needs setup"

def _state_label(value: str) -> str:
    return "SET" if str(value or "").strip() else "EMPTY"

def _bool_label(enabled: bool) -> str:
    return "ON" if enabled else "OFF"

def _token_mode_label(mode: str) -> str:
    raw = str(mode or "").strip().lower()
    return "HEMAT" if raw == "hemat" else "BOROS"

def _is_interactive_tty() -> bool:
    return bool(
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stdout, "isatty", lambda: False)()
    )

def _is_secret_env_name(env_key: str) -> bool:
    upper = str(env_key or "").upper()
    return any(token in upper for token in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"))

def _collect_skill_env_requirements(config: Any, skill_key: str) -> list[str]:
    from kabot.agent.skills import SkillsLoader

    key = str(skill_key or "").strip()
    if not key:
        return []
    try:
        loader = SkillsLoader(config.workspace_path, skills_config=config.skills)
        statuses = loader.list_skills(filter_unavailable=False)
    except Exception:
        return []

    status = next(
        (
            s
            for s in statuses
            if str(s.get("skill_key") or "").strip() == key
            or str(s.get("name") or "").strip() == key
        ),
        None,
    )
    if not isinstance(status, dict):
        return []

    env_keys: list[str] = []
    missing = status.get("missing", {})
    if isinstance(missing, dict):
        missing_env = missing.get("env", [])
        if isinstance(missing_env, list):
            for raw in missing_env:
                env = str(raw).strip()
                if env and env not in env_keys:
                    env_keys.append(env)

    primary = str(status.get("primaryEnv") or "").strip()
    if primary and primary not in env_keys:
        env_keys.append(primary)

    return env_keys

def _load_skill_persona_snippet(installed_dir: Path, skill_name: str, skill_key: str) -> str:
    candidates = [
        installed_dir / "soul-injection.md",
        installed_dir / "templates" / "soul-injection.md",
        installed_dir / "SOUL.md",
        installed_dir / "templates" / "SOUL.md",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            return text

    display_name = (skill_name or skill_key or "Skill").strip()
    return (
        f"## {display_name} Capability\n\n"
        f"When user requests tasks related to this capability, use `{skill_key}` skill."
    )

def _load_skill_agents_snippet(installed_dir: Path, skill_name: str, skill_key: str) -> str:
    candidates = [
        installed_dir / "agents-injection.md",
        installed_dir / "templates" / "agents-injection.md",
        installed_dir / "AGENTS.md",
        installed_dir / "templates" / "AGENTS.md",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            return text

    display_name = (skill_name or skill_key or "Skill").strip()
    return (
        f"## {display_name} Skill Routing\n\n"
        f"For tasks related to this capability, prioritize `{skill_key}` when appropriate."
    )

def _extract_skill_capability_summary(installed_dir: Path, fallback: str) -> str:
    skill_md = installed_dir / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception:
        return fallback

    content = text.strip()
    if not content:
        return fallback

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            for line in frontmatter.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                if key.strip().lower() != "description":
                    continue
                parsed = value.strip().strip('"').strip("'")
                if parsed:
                    return parsed
            content = parts[2].strip()

    for line in content.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("#"):
            clean = clean.lstrip("#").strip()
            if clean:
                return clean
            continue
        return clean
    return fallback

def _build_agents_persona_template(
    *,
    skill_name: str,
    skill_key: str,
    mode: str,
    capability_summary: str,
) -> str:
    display_name = (skill_name or skill_key or "Skill").strip()
    capability = (capability_summary or f"Tasks related to {display_name}").strip()
    template_mode = (mode or "minimal").strip().lower()
    if template_mode == "strict":
        return (
            f"## {display_name} Strict Routing Guardrails\n\n"
            f"- Scope: {capability}\n"
            f"- Prefer `{skill_key}` before generic workflows for matching requests.\n"
            "- If request is outside scope, continue with normal routing.\n"
            "- Never fabricate tool output; report blocked/missing prerequisites explicitly.\n"
        )
    if template_mode == "tools":
        return (
            f"## {display_name} Tool-First Routing\n\n"
            f"- Capability summary: {capability}\n"
            f"- For applicable requests, call `{skill_key}` and provide concise execution status.\n"
            "- If prerequisites are missing, request only required env/dependency details.\n"
            "- Keep responses operational and avoid redundant explanations.\n"
        )
    if template_mode == "custom":
        return (
            f"## {display_name} Routing Policy\n\n"
            f"- Policy: {capability}\n"
            f"- Apply `{skill_key}` when policy matches user intent.\n"
        )
    return (
        f"## {display_name} Skill Routing\n\n"
        f"- Capability summary: {capability}\n"
        f"- Prioritize `{skill_key}` when user asks within this scope.\n"
    )

def _choose_agents_persona_snippet(
    *,
    installed_dir: Path,
    skill_name: str,
    skill_key: str,
    default_snippet: str,
) -> str:
    if not Confirm.ask("*  Use AGENTS template assistant for this skill", default=False):
        return default_snippet

    choice = ClackUI.clack_select(
        "AGENTS template style",
        choices=[
            questionary.Choice("Use skill-provided snippet (recommended)", value="skill"),
            questionary.Choice("Minimal routing template", value="minimal"),
            questionary.Choice("Strict guardrails template", value="strict"),
            questionary.Choice("Tool-first routing template", value="tools"),
            questionary.Choice("Custom one-line routing policy", value="custom"),
            questionary.Choice("Back", value="back"),
        ],
        default="skill",
    )
    if choice in {None, "back", "skill"}:
        return default_snippet

    fallback_summary = f"Tasks related to {skill_name or skill_key}"
    capability_summary = _extract_skill_capability_summary(installed_dir, fallback_summary)
    if choice == "custom":
        policy = Prompt.ask(
            "|  Describe AGENTS routing focus",
            default=capability_summary,
        ).strip()
        if not policy or policy.lower() == "back":
            return default_snippet
        capability_summary = policy
    return _build_agents_persona_template(
        skill_name=skill_name,
        skill_key=skill_key,
        mode=str(choice),
        capability_summary=capability_summary,
    )

def _inject_skill_persona(workspace: Path, snippet: str, target_file: str = "SOUL.md") -> bool:
    ensure_workspace_templates(workspace)
    target_path = workspace / target_file
    if not target_path.exists():
        target_path.write_text("", encoding="utf-8")
    current = target_path.read_text(encoding="utf-8")
    normalized_snippet = snippet.strip()
    if not normalized_snippet:
        return False
    if normalized_snippet in current:
        return False
    new_content = current.rstrip() + ("\n\n" if current.strip() else "") + normalized_snippet + "\n"
    target_path.write_text(new_content, encoding="utf-8")
    return True

def _preview_snippet(title: str, snippet: str) -> None:
    cleaned = snippet.strip()
    if not cleaned:
        return
    lines = cleaned.splitlines()
    if len(lines) > 24:
        preview = "\n".join(lines[:24]) + "\n... (truncated)"
    else:
        preview = cleaned
    console.print(f"|  [bold cyan]{title} preview[/bold cyan]")
    for line in preview.splitlines():
        console.print(f"|    {line}")

def _extract_skill_candidate_subdirs(error_text: str) -> list[str]:
    marker = "Candidates:"
    if marker not in error_text:
        return []
    tail = error_text.split(marker, 1)[1].strip()
    raw_items = [item.strip() for item in tail.split(",")]
    parsed: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item or item in seen:
            continue
        seen.add(item)
        parsed.append(item)
    return parsed

def _normalize_candidate_rows(candidates: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in candidates:
        if isinstance(item, dict):
            subdir = str(item.get("subdir") or "").strip()
            if not subdir:
                continue
            rows.append(
                {
                    "subdir": subdir,
                    "name": str(item.get("name") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                }
            )
            continue
        subdir = str(item or "").strip()
        if not subdir:
            continue
        rows.append({"subdir": subdir, "name": "", "description": ""})
    return rows

def _format_candidate_label(candidate: dict[str, str]) -> str:
    subdir = candidate.get("subdir", "")
    name = candidate.get("name", "")
    description = candidate.get("description", "")
    label = subdir
    if name:
        label = f"{subdir} - {name}"
    if description:
        compact = " ".join(description.split())
        if len(compact) > 72:
            compact = compact[:69].rstrip() + "..."
        label = f"{label} ({compact})"
    return label

def _prompt_skill_candidate_subdir(candidates: list[Any], current_subdir: str | None) -> str | None:
    candidate_rows = _normalize_candidate_rows(candidates)
    if not candidate_rows:
        return current_subdir

    choice_items = [
        questionary.Choice(_format_candidate_label(candidate), value=candidate["subdir"])
        for candidate in candidate_rows
    ]
    choice_items.extend(
        [
            questionary.Choice("Enter subdir manually", value="manual"),
            questionary.Choice("Back", value="back"),
        ]
    )
    subdirs = [candidate["subdir"] for candidate in candidate_rows]
    picked = ClackUI.clack_select(
        "Multiple skills found in repo. Select subdir",
        choices=choice_items,
        default=current_subdir if current_subdir in subdirs else subdirs[0],
    )
    if picked in {None, "back"}:
        console.print("|  [yellow]Cancelled[/yellow]")
        return None
    if picked == "manual":
        manual = Prompt.ask("|  Skill subdir", default=current_subdir or "").strip()
        if not manual or manual.lower() == "back":
            console.print("|  [yellow]Cancelled[/yellow]")
            return None
        return manual
    return str(picked).strip() or None

def _resolve_skill_install_target_dir(config: Any, target_value: str) -> Path:
    if target_value == "workspace":
        return config.workspace_path / "skills"

    load_settings = resolve_load_settings(config.skills)
    managed_dir = str(load_settings.get("managed_dir") or "").strip()
    if managed_dir:
        return Path(managed_dir).expanduser()
    return Path("~/.kabot/skills").expanduser()

def _wizard_install_external_skill(self) -> dict[str, Any] | None:
    from kabot.cli.skill_repo_installer import (
        install_skill_from_git,
        list_skill_candidate_details_from_git,
    )

    repo_url = Prompt.ask("|  Skill Git repo URL/path", default="").strip()
    if not repo_url or repo_url.lower() == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        return None

    ref = Prompt.ask("|  Git ref (optional)", default="").strip()
    if ref.lower() == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        return None

    subdir = Prompt.ask("|  Skill subdir (optional)", default="").strip()
    if subdir.lower() == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        return None

    name = Prompt.ask("|  Override skill name (optional)", default="").strip()
    if name.lower() == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        return None

    target_input = Prompt.ask(
        "|  Install target [managed/workspace]",
        default="managed",
    ).strip().lower()
    if target_input == "back":
        console.print("|  [yellow]Cancelled[/yellow]")
        return None
    target_value = target_input if target_input in {"managed", "workspace"} else "managed"
    target_dir = _resolve_skill_install_target_dir(self.config, target_value)

    selected_subdir = subdir or None
    if not selected_subdir:
        try:
            pre_candidates = list_skill_candidate_details_from_git(repo_url, ref or None)
        except ValueError as exc:
            console.print(f"|  [red]{exc}[/red]")
            return None
        if len(pre_candidates) > 1:
            selected_subdir = _prompt_skill_candidate_subdir(pre_candidates, selected_subdir)
            if selected_subdir is None:
                return None

    while True:
        try:
            installed = install_skill_from_git(
                repo_url=repo_url,
                target_dir=target_dir,
                ref=ref or None,
                subdir=selected_subdir,
                skill_name=name or None,
                overwrite=False,
            )
            break
        except ValueError as exc:
            error_text = str(exc)
            candidates = _extract_skill_candidate_subdirs(error_text)
            if not candidates:
                console.print(f"|  [red]{exc}[/red]")
                return None

            selected_subdir = _prompt_skill_candidate_subdir(candidates, selected_subdir)
            if selected_subdir is None:
                return None

    onboarding = resolve_onboarding_settings(self.config.skills)
    auto_enable = bool(onboarding.get("auto_enable_after_install", True))
    auto_prompt_env = bool(onboarding.get("auto_prompt_env", True))
    soul_mode = str(onboarding.get("soul_injection_mode", "prompt") or "prompt").strip().lower()
    if soul_mode not in {"disabled", "prompt", "auto"}:
        soul_mode = "prompt"

    if auto_enable:
        self.config.skills = set_skill_entry_enabled(
            self.config.skills,
            installed.skill_key,
            True,
            persist_true=True,
        )

    saved_env_keys: list[str] = []
    if auto_prompt_env:
        env_keys = _resolve_tools_section_override(
            "_collect_skill_env_requirements",
            _collect_skill_env_requirements,
        )(self.config, installed.skill_key)
        for env_key in env_keys:
            if not Confirm.ask(f"*  Set {env_key} for {installed.skill_name}", default=True):
                continue
            current_val = os.environ.get(env_key) or ""
            value = Prompt.ask(
                f"|  Enter {env_key}",
                default=current_val,
                password=_is_secret_env_name(env_key),
            )
            val = str(value or "").strip()
            if not val:
                continue
            self.config.skills = set_skill_entry_env(self.config.skills, installed.skill_key, env_key, val)
            if env_key not in saved_env_keys:
                saved_env_keys.append(env_key)
            if env_key not in os.environ:
                os.environ[env_key] = val

    persona_injected = False
    persona_targets: list[str] = []
    if soul_mode != "disabled":
        soul_snippet = _load_skill_persona_snippet(
            installed.installed_dir,
            installed.skill_name,
            installed.skill_key,
        )
        agents_snippet = _load_skill_agents_snippet(
            installed.installed_dir,
            installed.skill_name,
            installed.skill_key,
        )
        if soul_mode == "auto":
            if _inject_skill_persona(self.config.workspace_path, soul_snippet, target_file="SOUL.md"):
                persona_injected = True
                persona_targets.append("SOUL.md")
            if _inject_skill_persona(self.config.workspace_path, agents_snippet, target_file="AGENTS.md"):
                persona_injected = True
                persona_targets.append("AGENTS.md")
        else:
            if Confirm.ask("*  Preview persona snippets before apply", default=True):
                _preview_snippet("SOUL.md", soul_snippet)
                _preview_snippet("AGENTS.md", agents_snippet)
            if Confirm.ask(
                f"*  Inject persona snippet into SOUL.md for '{installed.skill_name}'",
                default=True,
            ):
                if _inject_skill_persona(self.config.workspace_path, soul_snippet, target_file="SOUL.md"):
                    persona_injected = True
                    persona_targets.append("SOUL.md")
            if Confirm.ask(
                f"*  Inject persona snippet into AGENTS.md for '{installed.skill_name}'",
                default=False,
            ):
                selected_agents_snippet = _choose_agents_persona_snippet(
                    installed_dir=installed.installed_dir,
                    skill_name=installed.skill_name,
                    skill_key=installed.skill_key,
                    default_snippet=agents_snippet,
                )
                if _inject_skill_persona(self.config.workspace_path, selected_agents_snippet, target_file="AGENTS.md"):
                    persona_injected = True
                    persona_targets.append("AGENTS.md")

    console.print(f"|  [green]OK[/green] Installed skill from git: {installed.skill_name}")
    console.print(f"|  [dim]Source: {installed.repo_url}[/dim]")
    console.print(f"|  [dim]Installed: {installed.installed_dir}[/dim]")
    if auto_enable:
        console.print(f"|  [dim]Enabled in config: skills.entries.{installed.skill_key}.enabled=true[/dim]")
    if saved_env_keys:
        console.print(f"|  [dim]Saved env keys: {', '.join(saved_env_keys)}[/dim]")
    if persona_injected:
        targets = ", ".join(persona_targets) if persona_targets else "SOUL.md"
        console.print(f"|  [dim]Persona snippet injected into {targets}[/dim]")

    return {
        "skill_name": installed.skill_name,
        "skill_key": installed.skill_key,
        "saved_env_keys": saved_env_keys,
        "persona_injected": persona_injected,
        "persona_targets": persona_targets,
    }

def _set_install_settings(skills_cfg: Any, **kwargs: Any) -> Any:
    normalized = normalize_skills_settings(skills_cfg)
    install = normalized.setdefault("install", {})
    for key, value in kwargs.items():
        install[key] = value
    if hasattr(skills_cfg, "model_dump"):
        try:
            from kabot.config.schema import SkillsConfig

            return SkillsConfig.from_raw(normalized)
        except Exception:
            return normalized
    return normalized

def _install_step_hint(spec: dict[str, Any]) -> str:
    kind = str(spec.get("kind") or "").strip().lower()
    if kind == "node":
        package = str(spec.get("package") or "").strip()
        return package or "node package"
    if kind == "brew":
        formula = str(spec.get("formula") or "").strip()
        return formula or "brew formula"
    if kind == "go":
        module = str(spec.get("module") or "").strip()
        return module or "go module"
    if kind == "uv":
        package = str(spec.get("package") or "").strip()
        return package or "uv package"
    if kind == "download":
        return str(spec.get("url") or "").strip() or "download"
    return str(spec.get("cmd") or "").strip() or "manual command"

def _print_manual_install_plan(skill: dict[str, Any]) -> None:
    skill_name = str(skill.get("name") or "").strip() or "unknown-skill"
    install_specs = skill.get("install")
    missing_bins = skill.get("missing", {}).get("bins", []) if isinstance(skill.get("missing"), dict) else []

    console.print(f"|  [cyan]Install plan for {skill_name}[/cyan]")
    if isinstance(install_specs, list) and install_specs:
        for spec in install_specs:
            if not isinstance(spec, dict):
                continue
            label = str(spec.get("label") or "").strip() or _install_step_hint(spec)
            cmd = str(spec.get("cmd") or "").strip()
            console.print(f"|    - {label}")
            if cmd:
                console.print(f"|      [dim]{cmd}[/dim]")
    elif missing_bins:
        console.print("|    - Install required binaries manually:")
        for bin_name in missing_bins:
            console.print(f"|      [dim]{bin_name}[/dim]")
    else:
        console.print("|    - [dim]No install metadata found; follow skill docs.[/dim]")

    console.print("|    [dim]Tip: run `kabot doctor --fix` after installing dependencies.[/dim]")
    console.print("|    [dim]Docs: HOW_TO_USE.MD#skills[/dim]")

def _best_search_provider_from_keys(self) -> str:
    if str(self.config.tools.web.search.perplexity_api_key or "").strip():
        return "perplexity"
    if str(self.config.tools.web.search.kimi_api_key or "").strip():
        return "kimi"
    if str(self.config.tools.web.search.xai_api_key or "").strip():
        return "grok"
    return "brave"
