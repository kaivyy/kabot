from pathlib import Path

from kabot.core.command_router import CommandRouter
from kabot.core.command_surfaces import build_command_surface_specs


def _normalize(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("/"):
        raw = raw[1:]
    return raw.strip().lower().replace("-", "_").replace(" ", "_")


def _is_valid(value: str) -> bool:
    return bool(value)


def test_build_command_surface_specs_merges_static_router_and_workspace_skills(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "cek-runtime-vps"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: cek-runtime-vps\ndescription: Check VPS runtime quickly\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    router = CommandRouter()

    async def dummy_handler(ctx):
        return "ok"

    router.register("/status", dummy_handler, "Show status")

    class _Loader:
        def __init__(self, _workspace):
            pass

        def list_skills(self, filter_unavailable=True):
            return [{"name": "cek-runtime-vps", "description": "Check VPS runtime quickly"}]

    monkeypatch.setattr("kabot.core.command_surfaces.SkillsLoader", _Loader)

    specs = build_command_surface_specs(
        static_commands=[("start", "Start the bot"), ("help", "Show help")],
        router=router,
        workspace=workspace,
        normalize_name=_normalize,
        is_valid_name=_is_valid,
    )

    assert [(spec.name, spec.source) for spec in specs] == [
        ("start", "static"),
        ("help", "static"),
        ("status", "router"),
        ("cek_runtime_vps", "skill"),
    ]


def test_build_command_surface_specs_skips_skill_name_collisions(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    skill_dir = workspace / "skills" / "status"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: status\ndescription: Status skill\n---\n\n# Skill\n",
        encoding="utf-8",
    )

    router = CommandRouter()

    async def dummy_handler(ctx):
        return "ok"

    router.register("/status", dummy_handler, "Show status")

    class _Loader:
        def __init__(self, _workspace):
            pass

        def list_skills(self, filter_unavailable=True):
            return [{"name": "status", "description": "Status skill"}]

    monkeypatch.setattr("kabot.core.command_surfaces.SkillsLoader", _Loader)

    specs = build_command_surface_specs(
        static_commands=[("start", "Start the bot")],
        router=router,
        workspace=workspace,
        normalize_name=_normalize,
        is_valid_name=_is_valid,
    )

    assert [spec.name for spec in specs] == ["start", "status"]


def test_build_command_surface_specs_respects_skill_invocation_policy(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"

    hidden_skill_dir = workspace / "skills" / "hidden-skill"
    hidden_skill_dir.mkdir(parents=True, exist_ok=True)
    (hidden_skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: hidden-skill\n"
            "description: Hidden skill\n"
            "user-invocable: false\n"
            "---\n\n"
            "# Skill\n"
        ),
        encoding="utf-8",
    )

    dispatch_skill_dir = workspace / "skills" / "meta-threads-official"
    dispatch_skill_dir.mkdir(parents=True, exist_ok=True)
    (dispatch_skill_dir / "SKILL.md").write_text(
        (
            "---\n"
            "name: meta-threads-official\n"
            "description: Post to Meta Threads\n"
            "user-invocable: true\n"
            "command-dispatch: tool\n"
            "command-tool: meta_threads_post\n"
            "---\n\n"
            "# Skill\n"
        ),
        encoding="utf-8",
    )

    class _Loader:
        def __init__(self, _workspace):
            pass

        def list_skills(self, filter_unavailable=True):
            return [
                {
                    "name": "hidden-skill",
                    "description": "Hidden skill",
                    "user_invocable": False,
                },
                {
                    "name": "meta-threads-official",
                    "description": "Post to Meta Threads",
                    "user_invocable": True,
                    "command_dispatch": "tool",
                    "command_tool": "meta_threads_post",
                    "command_arg_mode": "raw",
                },
            ]

    monkeypatch.setattr("kabot.core.command_surfaces.SkillsLoader", _Loader)

    specs = build_command_surface_specs(
        static_commands=[("start", "Start the bot")],
        router=None,
        workspace=workspace,
        normalize_name=_normalize,
        is_valid_name=_is_valid,
    )

    assert [spec.name for spec in specs] == ["start", "meta_threads_official"]
    skill_spec = specs[-1]
    assert skill_spec.source == "skill"
    assert skill_spec.skill_name == "meta-threads-official"
    assert skill_spec.command_dispatch == "tool"
    assert skill_spec.command_tool == "meta_threads_post"
