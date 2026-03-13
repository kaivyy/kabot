from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from loguru import logger

from kabot.agent.skills import SkillsLoader


@dataclass(frozen=True)
class CommandSurfaceSpec:
    name: str
    description: str
    source: str
    skill_name: str = ""
    admin_only: bool = False
    command_dispatch: str = ""
    command_tool: str = ""
    command_arg_mode: str = "raw"


def normalize_slash_command_name(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("/"):
        raw = raw[1:]
    raw = raw.split("@", 1)[0]
    return raw.strip().lower().replace("-", "_").replace(" ", "_")


def is_basic_slash_command_name(value: str) -> bool:
    return bool(value)


def list_router_command_specs(
    router: Any,
    *,
    normalize_name: Callable[[str], str],
    is_valid_name: Callable[[str], bool],
) -> list[CommandSurfaceSpec]:
    if not router or not hasattr(router, "_commands"):
        return []

    specs: list[CommandSurfaceSpec] = []
    for raw_cmd_name, registration in getattr(router, "_commands", {}).items():
        command_name = normalize_name(raw_cmd_name)
        if not command_name or not is_valid_name(command_name):
            logger.warning(f"Skipping invalid command surface name: {raw_cmd_name!r}")
            continue
        specs.append(
            CommandSurfaceSpec(
                name=command_name,
                description=str(getattr(registration, "description", "") or "").strip(),
                source="router",
                admin_only=bool(getattr(registration, "admin_only", False)),
            )
        )
    return sorted(specs, key=lambda item: item.name)


def list_workspace_skill_command_specs(
    workspace: Path | None,
    *,
    normalize_name: Callable[[str], str],
    is_valid_name: Callable[[str], bool],
    reserved: set[str] | None = None,
) -> list[CommandSurfaceSpec]:
    if not isinstance(workspace, Path) or not workspace.exists():
        return []

    try:
        loader = SkillsLoader(workspace)
        skills = loader.list_skills(filter_unavailable=True)
    except Exception as exc:
        logger.debug(f"Failed to list workspace skills for command surfaces: {exc}")
        return []

    used = {normalize_name(name) for name in (reserved or set())}
    specs: list[CommandSurfaceSpec] = []
    for skill in skills:
        skill_name = str(skill.get("name") or "").strip()
        if not skill_name:
            continue
        if not bool(skill.get("user_invocable", True)):
            continue
        command_name = normalize_name(skill_name)
        if not command_name or not is_valid_name(command_name):
            continue
        if command_name in used:
            continue
        description = str(skill.get("description") or f"Use {skill_name} skill").strip()
        if not description:
            description = f"Use {skill_name} skill"
        used.add(command_name)
        specs.append(
            CommandSurfaceSpec(
                name=command_name,
                description=description[:256],
                source="skill",
                skill_name=skill_name,
                admin_only=False,
                command_dispatch=str(skill.get("command_dispatch") or "").strip(),
                command_tool=str(skill.get("command_tool") or "").strip(),
                command_arg_mode=str(skill.get("command_arg_mode") or "raw").strip() or "raw",
            )
        )
    return sorted(specs, key=lambda item: item.name)


def build_command_surface_specs(
    *,
    static_commands: Iterable[tuple[str, str]],
    router: Any,
    workspace: Path | None,
    normalize_name: Callable[[str], str],
    is_valid_name: Callable[[str], bool],
    max_commands: int | None = None,
) -> list[CommandSurfaceSpec]:
    specs: list[CommandSurfaceSpec] = []
    reserved: set[str] = set()

    for raw_name, description in static_commands:
        command_name = normalize_name(raw_name)
        if not command_name or not is_valid_name(command_name):
            continue
        specs.append(
            CommandSurfaceSpec(
                name=command_name,
                description=str(description or "").strip(),
                source="static",
                admin_only=False,
            )
        )
        reserved.add(command_name)

    router_specs = list_router_command_specs(
        router,
        normalize_name=normalize_name,
        is_valid_name=is_valid_name,
    )
    for spec in router_specs:
        if spec.name in reserved:
            continue
        specs.append(spec)
        reserved.add(spec.name)

    for spec in list_workspace_skill_command_specs(
        workspace,
        normalize_name=normalize_name,
        is_valid_name=is_valid_name,
        reserved=reserved,
    ):
        if spec.name in reserved:
            continue
        specs.append(spec)
        reserved.add(spec.name)

    if max_commands is not None and len(specs) > max_commands:
        return specs[:max_commands]
    return specs


def format_command_surface_help_text(
    specs: Iterable[CommandSurfaceSpec],
    *,
    title: str = "*Available Commands:*\n",
) -> str:
    items = list(specs)
    if not items:
        return "No commands registered."

    lines = [title]
    non_skill = [spec for spec in items if spec.source != "skill"]
    skill = [spec for spec in items if spec.source == "skill"]

    for spec in non_skill:
        admin_badge = " [admin]" if spec.admin_only else ""
        lines.append(f"  `/{spec.name}` - {spec.description}{admin_badge}")
    if skill:
        lines.append("")
        lines.append("*Skills:*")
        for spec in skill:
            lines.append(f"  `/{spec.name}` - {spec.description}")
    return "\n".join(lines)
