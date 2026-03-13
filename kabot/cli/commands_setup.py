"""Extracted CLI command helpers from kabot.cli.commands."""

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from kabot import __logo__
from kabot.utils.workspace_templates import ensure_workspace_templates

console = Console()


def _skill_lock_path_for_target(config, target: str) -> Path:
    from kabot.cli.skill_lock import resolve_skill_lock_path

    return resolve_skill_lock_path(workspace=config.workspace_path, target=target)


def _resolve_commands_override(name: str, fallback):
    try:
        from kabot.cli import commands as commands_module
    except Exception:
        return fallback
    return getattr(commands_module, name, fallback)

def onboard():
    """Initialize kabot configuration and workspace."""
    from kabot.config.loader import get_config_path, save_config
    from kabot.config.schema import Config
    from kabot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()

    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")

    # Create default bootstrap files
    _create_workspace_templates(workspace)

    console.print(f"\n{__logo__} kabot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.kabot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]kabot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/kaivyy/kabot#-chat-apps[/dim]")

def google_auth(
    credentials_path: str = typer.Argument(
        ..., help="Path to the downloaded google_credentials.json file."
    )
):
    """Setup Google Suite OAuth credentials interactively."""
    from pathlib import Path

    from kabot.auth.google_auth import GoogleAuthManager

    cred_file = Path(credentials_path)
    if not cred_file.exists():
        console.print(f"[red]Error: Credentials file not found at {cred_file}[/red]")
        raise typer.Exit(1)

    auth_manager = GoogleAuthManager()

    # Copy credentials to the workspace
    target_path = auth_manager.credentials_path
    try:
        shutil.copy(cred_file, target_path)
        console.print(f"[green]✓[/green] Copied credentials to {target_path}")
    except Exception as e:
        console.print(f"[red]Failed to copy credentials: {e}[/red]")
        raise typer.Exit(1)

    # Trigger auth flow
    console.print("[cyan]Initiating Google OAuth login flow in your browser...[/cyan]")
    try:
        auth_manager.get_credentials()
        console.print("[green]✓[/green] Successfully authenticated with Google Suite!")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        raise typer.Exit(1)

def train(
    file_path: str = typer.Argument(
        ..., help="Path to the .pdf, .txt, or .md file to train the agent on."
    ),
    workspace: str = typer.Option(
        "cli", "--workspace", "-w", help="Workspace to inject the memory into (e.g. Aizawa, Hawk)."
    )
):
    """Auto-Onboard an agent by uploading a document directly into its memory."""
    from pathlib import Path

    from kabot.memory.chroma_memory import ChromaMemoryManager
    from kabot.utils.document_parser import DocumentParser
    from kabot.utils.helpers import get_workspace_path

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: File not found at {path}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Reading document: {path.name}...[/cyan]")
    try:
        text = DocumentParser.extract_text(path)
        chunks = DocumentParser.chunk_text(text, chunk_size=1500, overlap=300)
    except Exception as e:
        console.print(f"[red]Failed to extract text: {e}[/red]")
        raise typer.Exit(1)

    if not chunks:
        console.print("[yellow]No text could be extracted from the file.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[cyan]Extracted {len(chunks)} chunks. Injecting into workspace '{workspace}'...[/cyan]")

    # Initialize chroma DB for the specific workspace
    base_dir = get_workspace_path()
    chroma_dir = base_dir / "sessions" / workspace / "chroma"
    chroma_manager = ChromaMemoryManager(persist_directory=str(chroma_dir))

    try:
        # Save each chunk as a memory
        for i, chunk in enumerate(chunks):
            # Prefix it to signify it's training data, not conversation history
            doc_content = f"Training Reference ({path.name} part {i+1}): {chunk}"
            # Inject it
            chroma_manager.add_messages([
                {"role": "system", "content": doc_content}
            ])

        console.print(f"[green]✓[/green] Successfully trained '{workspace}' with {len(chunks)} chunks from {path.name}!")
    except Exception as e:
        console.print(f"[red]Memory injection failed: {e}[/red]")
        raise typer.Exit(1)

def setup(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Run interactive setup wizard"),
):
    """Interactive setup wizard for configuring kabot."""
    from kabot.config.loader import get_config_path, save_config

    config_path = get_config_path()

    if interactive:
        from kabot.cli.setup_wizard import run_interactive_setup

        console.print(f"\n{__logo__} [bold cyan]Welcome to Kabot Setup![/bold cyan]\n")

        if config_path.exists():
            console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
            if not typer.confirm("Run setup wizard to reconfigure?"):
                raise typer.Exit()

        # Run interactive wizard
        config = run_interactive_setup()

        # Save configuration
        save_config(config)
        console.print(f"\n[green]✓ Configuration saved to {config_path}[/green]")

        # Create workspace and templates
        workspace = Path(config.agents.defaults.workspace).expanduser()
        _create_workspace_templates(workspace)
        console.print(f"[green]✓ Workspace ready at {workspace}[/green]")

        # Show next steps
        console.print(f"\n{__logo__} Kabot is configured!\n")
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Start gateway: [cyan]kabot gateway[/cyan]")
        console.print("  2. Test agent: [cyan]kabot agent -m 'Hello!'[/cyan]")
        console.print("  3. Auto-start: [cyan]See deployment/README.md[/cyan]\n")
    else:
        # Fallback to old onboard behavior
        onboard()

def config(
    edit: bool = typer.Option(False, "--edit", "-e", help="Open configuration file in default editor"),
    token_mode: str = typer.Option(
        "",
        "--token-mode",
        help="Set runtime token mode directly: boros or hemat",
    ),
    token_saver: bool | None = typer.Option(
        None,
        "--token-saver/--no-token-saver",
        help="Shortcut toggle: enabled=hemat, disabled=boros",
    ),
):
    """Configure kabot settings."""
    from kabot.config.loader import get_config_path, load_config, save_config

    if str(token_mode or "").strip() or token_saver is not None:
        raw_mode = str(token_mode or "").strip().lower()
        if raw_mode:
            if raw_mode not in {"boros", "hemat"}:
                raise typer.BadParameter("Token mode must be boros or hemat.", param_hint="--token-mode")
            resolved_mode = raw_mode
        else:
            resolved_mode = "hemat" if bool(token_saver) else "boros"

        cfg = load_config()
        cfg.runtime.performance.token_mode = resolved_mode
        save_config(cfg)
        console.print(f"[green]Runtime token mode set to {resolved_mode.upper()}[/green]")
        return

    if edit:
        config_path = get_config_path()
        if not config_path.exists():
            console.print(f"[yellow]Config not found at {config_path}. Running setup first...[/yellow]")
            _resolve_commands_override("setup", setup)(interactive=True)
            return

        console.print(f"Opening {config_path}...")
        typer.launch(str(config_path))
    else:
        _resolve_commands_override("setup", setup)(interactive=True)

def _is_secret_env_name(env_key: str) -> bool:
    upper = str(env_key or "").upper()
    return any(token in upper for token in ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"))

def _collect_skill_env_requirements(config, skill_key: str) -> list[str]:
    """Collect required env keys for a specific installed skill."""
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
    """Load optional skill persona snippet, fallback to generic snippet."""
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

def _inject_skill_persona(workspace: Path, snippet: str) -> bool:
    """Append persona snippet to SOUL.md once."""
    ensure_workspace_templates(workspace)
    soul_path = workspace / "SOUL.md"
    if not soul_path.exists():
        soul_path.write_text("", encoding="utf-8")
    current = soul_path.read_text(encoding="utf-8")
    normalized_snippet = snippet.strip()
    if not normalized_snippet:
        return False
    if normalized_snippet in current:
        return False
    new_content = current.rstrip() + ("\n\n" if current.strip() else "") + normalized_snippet + "\n"
    soul_path.write_text(new_content, encoding="utf-8")
    return True

def _handle_skill_onboarding(config, installed) -> dict[str, Any]:
    """Apply one-shot onboarding: auto-enable, env prompts, and persona injection."""
    from kabot.config.skills_settings import (
        resolve_onboarding_settings,
        set_skill_entry_enabled,
        set_skill_entry_env,
    )

    onboarding = resolve_onboarding_settings(config.skills)
    auto_enable = bool(onboarding.get("auto_enable_after_install", True))
    auto_prompt_env = bool(onboarding.get("auto_prompt_env", True))
    soul_mode = str(onboarding.get("soul_injection_mode", "prompt") or "prompt").strip().lower()
    if soul_mode not in {"disabled", "prompt", "auto"}:
        soul_mode = "prompt"

    if auto_enable:
        config.skills = set_skill_entry_enabled(
            config.skills,
            installed.skill_key,
            True,
            persist_true=True,
        )

    saved_env_keys: list[str] = []
    if auto_prompt_env:
        env_keys = _resolve_commands_override("_collect_skill_env_requirements", _collect_skill_env_requirements)(config, installed.skill_key)
        for env_key in env_keys:
            current_val = os.environ.get(env_key) or ""
            prompt_text = f"Enter {env_key}"
            value = typer.prompt(
                prompt_text,
                default=current_val,
                hide_input=_is_secret_env_name(env_key),
            )
            val = str(value or "").strip()
            if not val:
                continue
            config.skills = set_skill_entry_env(config.skills, installed.skill_key, env_key, val)
            if env_key not in saved_env_keys:
                saved_env_keys.append(env_key)
            if env_key not in os.environ:
                os.environ[env_key] = val

    persona_injected = False
    if soul_mode != "disabled":
        should_inject = soul_mode == "auto"
        if soul_mode == "prompt":
            if sys.stdin.isatty() and sys.stdout.isatty():
                should_inject = typer.confirm(
                    f"Inject persona snippet into SOUL.md for '{installed.skill_name}'?",
                    default=True,
                )
            else:
                should_inject = False
        if should_inject:
            snippet = _load_skill_persona_snippet(
                installed.installed_dir,
                installed.skill_name,
                installed.skill_key,
            )
            persona_injected = _inject_skill_persona(config.workspace_path, snippet)

    return {
        "auto_enabled": auto_enable,
        "saved_env_keys": saved_env_keys,
        "persona_injected": persona_injected,
    }

def skills_install(
    slug: str = typer.Argument("", help="Catalog skill slug to install"),
    git: str = typer.Option("", "--git", help="Git repository URL/path that contains SKILL.md"),
    path: str = typer.Option("", "--path", help="Local skill directory or packaged .skill/.zip bundle"),
    url: str = typer.Option("", "--url", help="Remote .skill/.zip bundle URL from any registry or host"),
    catalog_source: str = typer.Option(
        "builtin",
        "--catalog-source",
        help="Catalog source: builtin, a local JSON file path, or a JSON URL",
    ),
    ref: str = typer.Option("", "--ref", help="Optional git ref (tag/branch/commit)"),
    subdir: str = typer.Option(
        "",
        "--subdir",
        help="Relative folder in repo containing SKILL.md (required when repo has multiple skills)",
    ),
    name: str = typer.Option("", "--name", help="Override installed skill name/slug"),
    target: str = typer.Option("managed", "--target", help="Install target: managed or workspace"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing destination"),
):
    """Install an external skill from a catalog, git, or local source into Kabot."""
    from kabot.cli.skill_catalog import resolve_catalog_skill
    from kabot.cli.skill_lock import record_installed_skill
    from kabot.cli.skill_repo_installer import (
        install_skill_from_git,
        install_skill_from_path,
        install_skill_from_url,
    )
    from kabot.config.loader import load_config, save_config
    from kabot.config.schema import SkillsConfig
    from kabot.config.skills_settings import (
        normalize_skills_settings,
        resolve_load_settings,
        resolve_onboarding_settings,
    )
    from kabot.utils.skill_validator import validate_skill_trust

    cfg = load_config()
    slug_value = str(slug or "").strip()
    git_value = str(git or "").strip()
    path_value = str(path or "").strip()
    url_value = str(url or "").strip()
    chosen_sources = sum(bool(value) for value in (slug_value, git_value, path_value, url_value))
    if chosen_sources != 1:
        console.print("[red]Provide exactly one source: <slug>, --git, --path, or --url[/red]")
        raise typer.Exit(1)

    target_value = target.strip().lower()
    if target_value not in {"managed", "workspace"}:
        console.print("[red]Invalid --target. Use: managed or workspace[/red]")
        raise typer.Exit(1)

    if target_value == "workspace":
        target_dir = cfg.workspace_path / "skills"
    else:
        load_settings = resolve_load_settings(cfg.skills)
        managed_dir = str(load_settings.get("managed_dir") or "").strip()
        if managed_dir:
            target_dir = Path(managed_dir).expanduser()
        else:
            target_dir = Path("~/.kabot/skills").expanduser()

    try:
        if slug_value:
            entry = resolve_catalog_skill(slug_value, source=catalog_source)
            if not entry:
                raise ValueError(f"Catalog skill not found: {slug_value}")
            install_spec = entry.get("install", {})
            if not isinstance(install_spec, dict):
                raise ValueError(f"Catalog skill has no install spec: {slug_value}")
            git_value = str(install_spec.get("git") or "").strip()
            path_value = str(install_spec.get("path") or "").strip()
            url_value = str(install_spec.get("url") or "").strip()
            if not git_value and not path_value and not url_value:
                raise ValueError(f"Catalog skill has no installable source: {slug_value}")
            if not ref.strip():
                ref = str(install_spec.get("ref") or "").strip()
            if not subdir.strip():
                subdir = str(install_spec.get("subdir") or "").strip()

        if git_value:
            installed = install_skill_from_git(
                repo_url=git_value,
                target_dir=target_dir,
                ref=ref.strip() or None,
                subdir=subdir.strip() or None,
                skill_name=name.strip() or None,
                overwrite=force,
            )
        elif url_value:
            installed = install_skill_from_url(
                source_url=url_value,
                target_dir=target_dir,
                subdir=subdir.strip() or None,
                skill_name=name.strip() or None,
                overwrite=force,
            )
        else:
            installed = install_skill_from_path(
                source_path=path_value,
                target_dir=target_dir,
                subdir=subdir.strip() or None,
                skill_name=name.strip() or None,
                overwrite=force,
            )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    trust_mode = getattr(getattr(cfg, "security", None), "trust_mode", None)
    trust_enabled = bool(getattr(trust_mode, "enabled", False))
    if trust_enabled:
        trust_ok, trust_detail = validate_skill_trust(
            installed.installed_dir,
            verify_skill_manifest=bool(getattr(trust_mode, "verify_skill_manifest", False)),
            allowed_signers=list(getattr(trust_mode, "allowed_signers", []) or []),
        )
        if not trust_ok:
            try:
                import shutil
                shutil.rmtree(installed.installed_dir, ignore_errors=True)
            except Exception:
                pass
            console.print(f"[red]Trust mode blocked skill install: {trust_detail}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Trust mode verified[/green]: {trust_detail}")

    onboarding = resolve_onboarding_settings(cfg.skills)
    auto_enable = bool(onboarding.get("auto_enable_after_install", True))
    onboarding_result = _handle_skill_onboarding(cfg, installed)
    cfg.skills = SkillsConfig.from_raw(cfg.skills)
    save_config(cfg)

    if slug_value:
        source_type = "catalog"
        source_value = slug_value
    elif git_value:
        source_type = "git"
        source_value = git_value
    elif url_value:
        source_type = "url"
        source_value = url_value
    else:
        source_type = "path"
        source_value = path_value
    record_installed_skill(
        lock_path=_skill_lock_path_for_target(cfg, target_value),
        installed=installed,
        target=target_value,
        source_type=source_type,
        source_value=source_value,
        catalog_slug=slug_value,
        catalog_source=catalog_source if slug_value else "",
        ref=ref.strip(),
        subdir=subdir.strip(),
    )

    console.print(f"[green]✓[/green] Installed skill: [cyan]{installed.skill_name}[/cyan]")
    if slug_value:
        console.print(f"  Catalog slug: {slug_value}")
        console.print(f"  Catalog source: {catalog_source}")
        source_label = "Catalog install source"
    else:
        source_label = "Source repo" if git_value else "Source URL" if url_value else "Source path"
    console.print(f"  {source_label}: {installed.repo_url}")
    console.print(f"  Source dir: {installed.selected_dir}")
    console.print(f"  Installed to: {installed.installed_dir}")
    if auto_enable:
        console.print("  Enabled in config: skills.entries.{0}.enabled=true".format(installed.skill_key))
    else:
        console.print("  Auto-enable after install is OFF (skills.onboarding.autoEnableAfterInstall=false).")
    saved_env_keys = onboarding_result.get("saved_env_keys", [])
    if saved_env_keys:
        console.print(f"  Saved env keys: {', '.join(saved_env_keys)}")
    if onboarding_result.get("persona_injected"):
        console.print("  Persona snippet injected into SOUL.md")
    console.print("\nNext:")
    console.print("  1. Run [cyan]kabot config[/cyan] -> Skills to configure env keys/dependency plan")
    console.print("  2. Run [cyan]kabot doctor[/cyan] to verify runtime requirements")


def skills_list(
    target: str = typer.Option(
        "all",
        "--target",
        help="Which lock view to inspect: workspace, managed, or all",
    ),
):
    """List installed skills recorded in Kabot lockfiles."""
    from kabot.cli.skill_lock import list_locked_skills
    from kabot.config.loader import load_config

    cfg = load_config()
    target_value = str(target or "").strip().lower()
    if target_value not in {"workspace", "managed", "all"}:
        console.print("[red]Invalid --target. Use: workspace, managed, or all[/red]")
        raise typer.Exit(1)

    targets = [target_value] if target_value != "all" else ["workspace", "managed"]
    rows: list[tuple[str, dict[str, Any]]] = []
    for scope in targets:
        lock_path = _skill_lock_path_for_target(cfg, scope)
        for item in list_locked_skills(lock_path):
            rows.append((scope, item))

    if not rows:
        console.print("[yellow]No installed skills recorded yet.[/yellow]")
        raise typer.Exit()

    console.print("[bold]Installed Skills[/bold]")
    for scope, item in rows:
        name = str(item.get("skill_name") or item.get("skill_key") or "").strip()
        source_type = str(item.get("source_type") or "unknown").strip()
        source_value = str(item.get("source_value") or "").strip()
        if not source_value:
            if source_type == "path":
                source_value = str(item.get("source_path") or "").strip()
            elif source_type == "url":
                source_value = str(item.get("source_url") or "").strip()
            elif source_type == "git":
                source_value = str(item.get("repo_url") or "").strip()
        console.print(f"- [cyan]{name}[/cyan] ({scope}, {source_type})")
        if source_value:
            console.print(f"  source: {source_value}")


def skills_update(
    slug: str = typer.Argument("", help="Specific installed skill to update"),
    target: str = typer.Option(
        "all",
        "--target",
        help="Which lock scope to update: workspace, managed, or all",
    ),
    all_skills: bool = typer.Option(False, "--all", help="Update every locked skill in the selected scope"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing destination"),
):
    """Reinstall skills from their recorded source, similar to registry update flows."""
    from kabot.cli.skill_catalog import resolve_catalog_skill
    from kabot.cli.skill_lock import get_locked_skill, list_locked_skills, record_installed_skill
    from kabot.cli.skill_repo_installer import (
        install_skill_from_git,
        install_skill_from_path,
        install_skill_from_url,
    )
    from kabot.config.loader import load_config, save_config

    cfg = load_config()
    target_value = str(target or "").strip().lower()
    if target_value not in {"workspace", "managed", "all"}:
        console.print("[red]Invalid --target. Use: workspace, managed, or all[/red]")
        raise typer.Exit(1)
    slug_value = str(slug or "").strip().lower()
    if not all_skills and not slug_value:
        console.print("[red]Provide a skill slug or use --all[/red]")
        raise typer.Exit(1)

    scopes = [target_value] if target_value != "all" else ["workspace", "managed"]
    selected: list[tuple[str, dict[str, Any]]] = []
    for scope in scopes:
        lock_path = _skill_lock_path_for_target(cfg, scope)
        if all_skills:
            selected.extend((scope, item) for item in list_locked_skills(lock_path))
        else:
            item = get_locked_skill(lock_path, slug_value)
            if item:
                selected.append((scope, item))
                break

    if not selected:
        console.print("[yellow]No matching locked skill entries found.[/yellow]")
        raise typer.Exit(1)

    updated_count = 0
    for scope, item in selected:
        source_type = str(item.get("source_type") or "").strip().lower()
        source_value = str(item.get("source_value") or "").strip()
        if not source_value:
            if source_type == "path":
                source_value = str(item.get("source_path") or "").strip()
            elif source_type == "url":
                source_value = str(item.get("source_url") or "").strip()
            elif source_type == "git":
                source_value = str(item.get("repo_url") or "").strip()
        catalog_slug = str(item.get("catalog_slug") or "").strip().lower()
        catalog_source = str(item.get("catalog_source") or "").strip() or "builtin"
        ref = str(item.get("ref") or "").strip()
        subdir = str(item.get("subdir") or "").strip()
        skill_name = str(item.get("skill_name") or item.get("skill_key") or "").strip()

        if scope == "workspace":
            target_dir = cfg.workspace_path / "skills"
        else:
            target_dir = Path(str(item.get("installed_dir") or "")).expanduser().resolve().parent

        try:
            if source_type == "catalog":
                entry = resolve_catalog_skill(catalog_slug, source=catalog_source)
                if not entry:
                    raise ValueError(f"Catalog skill not found: {catalog_slug}")
                install_spec = entry.get("install", {})
                if not isinstance(install_spec, dict):
                    raise ValueError(f"Catalog install spec missing for: {catalog_slug}")
                git_value = str(install_spec.get("git") or "").strip()
                path_value = str(install_spec.get("path") or "").strip()
                url_value = str(install_spec.get("url") or "").strip()
                ref_value = ref or str(install_spec.get("ref") or "").strip()
                subdir_value = subdir or str(install_spec.get("subdir") or "").strip()
                if git_value:
                    installed = install_skill_from_git(
                        repo_url=git_value,
                        target_dir=target_dir,
                        ref=ref_value or None,
                        subdir=subdir_value or None,
                        skill_name=skill_name or None,
                        overwrite=True,
                    )
                elif url_value:
                    installed = install_skill_from_url(
                        source_url=url_value,
                        target_dir=target_dir,
                        subdir=subdir_value or None,
                        skill_name=skill_name or None,
                        overwrite=True,
                    )
                elif path_value:
                    installed = install_skill_from_path(
                        source_path=path_value,
                        target_dir=target_dir,
                        subdir=subdir_value or None,
                        skill_name=skill_name or None,
                        overwrite=True,
                    )
                else:
                    raise ValueError(f"Catalog skill has no installable source: {catalog_slug}")
                record_installed_skill(
                    lock_path=_skill_lock_path_for_target(cfg, scope),
                    installed=installed,
                    target=scope,
                    source_type="catalog",
                    source_value=catalog_slug,
                    catalog_slug=catalog_slug,
                    catalog_source=catalog_source,
                    ref=ref_value,
                    subdir=subdir_value,
                )
            elif source_type == "git":
                installed = install_skill_from_git(
                    repo_url=source_value,
                    target_dir=target_dir,
                    ref=ref or None,
                    subdir=subdir or None,
                    skill_name=skill_name or None,
                    overwrite=True,
                )
                record_installed_skill(
                    lock_path=_skill_lock_path_for_target(cfg, scope),
                    installed=installed,
                    target=scope,
                    source_type="git",
                    source_value=source_value,
                    ref=ref,
                    subdir=subdir,
                )
            elif source_type == "url":
                installed = install_skill_from_url(
                    source_url=source_value,
                    target_dir=target_dir,
                    subdir=subdir or None,
                    skill_name=skill_name or None,
                    overwrite=True,
                )
                record_installed_skill(
                    lock_path=_skill_lock_path_for_target(cfg, scope),
                    installed=installed,
                    target=scope,
                    source_type="url",
                    source_value=source_value,
                    subdir=subdir,
                )
            elif source_type == "path":
                installed = install_skill_from_path(
                    source_path=source_value,
                    target_dir=target_dir,
                    subdir=subdir or None,
                    skill_name=skill_name or None,
                    overwrite=True,
                )
                record_installed_skill(
                    lock_path=_skill_lock_path_for_target(cfg, scope),
                    installed=installed,
                    target=scope,
                    source_type="path",
                    source_value=source_value,
                    subdir=subdir,
                )
            else:
                raise ValueError(f"Unsupported locked source type: {source_type or 'unknown'}")
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        updated_count += 1
        console.print(f"[green]✓[/green] Updated skill: [cyan]{installed.skill_name}[/cyan]")
        console.print(f"  Source: {source_type} -> {source_value or catalog_slug}")

    save_config(cfg)
    console.print(f"\nUpdated {updated_count} skill(s).")


def skills_pack(
    skill_path: str = typer.Argument(..., help="Path to a local skill directory"),
    output_dir: str = typer.Option(".", "--output-dir", help="Directory for the generated .skill bundle"),
):
    """Package a local skill directory into a distributable .skill bundle."""
    from kabot.cli.skill_catalog_registry import package_skill_bundle

    try:
        bundle_path = package_skill_bundle(Path(skill_path), output_dir=Path(output_dir))
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Created skill bundle: [cyan]{bundle_path}[/cyan]")


def skills_publish(
    skill_path: str = typer.Argument(..., help="Path to a local skill directory"),
    catalog_source: str = typer.Option(..., "--catalog-source", help="Writable local JSON catalog file"),
    bundle_dir: str = typer.Option(
        "",
        "--bundle-dir",
        help="Directory where generated .skill bundles should be stored (default: <catalog>/bundles)",
    ),
    slug: str = typer.Option("", "--slug", help="Override published skill slug"),
    name: str = typer.Option("", "--name", help="Override published display name"),
    version: str = typer.Option("1.0.0", "--version", help="Skill version for this published bundle"),
    description: str = typer.Option("", "--description", help="Override published description"),
    homepage: str = typer.Option("", "--homepage", help="Override published homepage"),
    tags: str = typer.Option("latest", "--tags", help="Comma-separated tags"),
    changelog: str = typer.Option("", "--changelog", help="Changelog for this published version"),
    bundle_url_base: str = typer.Option(
        "",
        "--bundle-url-base",
        help="Optional URL base for emitted install.url entries instead of local install.path entries",
    ),
):
    """Publish a local skill into a generic JSON catalog plus a .skill bundle."""
    from kabot.cli.skill_catalog_registry import publish_skill_to_catalog, resolve_catalog_write_path

    try:
        catalog_path = resolve_catalog_write_path(catalog_source)
        bundle_root = (
            Path(bundle_dir).expanduser()
            if str(bundle_dir or "").strip()
            else catalog_path.parent / "bundles"
        )
        entry, bundle_path = publish_skill_to_catalog(
            Path(skill_path),
            catalog_source=catalog_path,
            bundle_dir=bundle_root,
            slug=slug,
            name=name,
            version=version,
            description=description,
            homepage=homepage,
            tags=[item.strip() for item in str(tags or "").split(",") if item.strip()],
            changelog=changelog,
            bundle_url_base=bundle_url_base,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Published skill: [cyan]{entry['slug']}[/cyan]")
    console.print(f"  Catalog: {catalog_path}")
    console.print(f"  Bundle: {bundle_path}")
    if entry["install"].get("url"):
        console.print(f"  Install URL: {entry['install']['url']}")
    else:
        console.print(f"  Install path: {entry['install']['path']}")


def skills_sync(
    catalog_source: str = typer.Option(..., "--catalog-source", help="Writable local JSON catalog file"),
    root: list[str] = typer.Option(
        None,
        "--root",
        help="Additional root(s) to scan for skill directories containing SKILL.md",
    ),
    bundle_dir: str = typer.Option(
        "",
        "--bundle-dir",
        help="Directory where generated .skill bundles should be stored (default: <catalog>/bundles)",
    ),
    all_skills: bool = typer.Option(False, "--all", help="Publish every discovered skill without prompting"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview discovered skills without writing"),
    version: str = typer.Option("1.0.0", "--version", help="Default version for published skills"),
    tags: str = typer.Option("latest", "--tags", help="Comma-separated tags"),
    bundle_url_base: str = typer.Option(
        "",
        "--bundle-url-base",
        help="Optional URL base for emitted install.url entries instead of local install.path entries",
    ),
):
    """Scan local skill roots and publish them into a generic JSON catalog."""
    from kabot.cli.skill_catalog_registry import resolve_catalog_write_path, sync_skill_roots_to_catalog
    from kabot.config.loader import load_config

    if not all_skills and not dry_run:
        console.print("[red]Use --all to publish or --dry-run to preview.[/red]")
        raise typer.Exit(1)

    cfg = load_config()
    catalog_path = resolve_catalog_write_path(catalog_source)
    bundle_root = (
        Path(bundle_dir).expanduser()
        if str(bundle_dir or "").strip()
        else catalog_path.parent / "bundles"
    )
    roots: list[Path] = []
    raw_roots = root or []
    if raw_roots:
        roots.extend(Path(item).expanduser() for item in raw_roots if str(item).strip())
    else:
        roots.append(cfg.workspace_path / "skills")
        managed_dir = Path.home() / ".kabot" / "skills"
        roots.append(managed_dir)

    try:
        entries, skipped = sync_skill_roots_to_catalog(
            roots=roots,
            catalog_source=catalog_path,
            bundle_dir=bundle_root,
            default_version=version,
            tags=[item.strip() for item in str(tags or "").split(",") if item.strip()],
            bundle_url_base=bundle_url_base,
            dry_run=dry_run,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if not entries:
        console.print("[yellow]No skills discovered in the selected roots.[/yellow]")
        raise typer.Exit()

    action = "Would publish" if dry_run else "Published"
    console.print(f"[bold]{action}[/bold] {len(entries)} skill(s):")
    for entry in entries:
        console.print(f"- [cyan]{entry['slug']}[/cyan] — {entry['description']}")
    for item in skipped:
        console.print(f"[yellow]Skipping invalid skill[/yellow]: {item['path']} ({item['reason']})")
    if not dry_run:
        console.print(f"  Catalog: {catalog_path}")
        console.print(f"  Bundles: {bundle_root}")


def skills_search(
    query: str = typer.Argument("", help="Search query for public skills"),
    catalog_source: str = typer.Option(
        "builtin",
        "--catalog-source",
        help="Catalog source: builtin, a local JSON file path, or a JSON URL",
    ),
    limit: int = typer.Option(10, "--limit", min=1, max=50, help="Maximum number of results"),
):
    """Search a public skill catalog."""
    from kabot.cli.skill_catalog import search_skill_catalog

    try:
        results = search_skill_catalog(query, source=catalog_source, limit=limit)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]No matching skills found.[/yellow]")
        raise typer.Exit()

    console.print(f"[bold]Skill Catalog[/bold] ({catalog_source})")
    for entry in results:
        console.print(f"- [cyan]{entry['slug']}[/cyan] — {entry['description']}")


def skills_info(
    slug: str = typer.Argument(..., help="Catalog slug to inspect"),
    catalog_source: str = typer.Option(
        "builtin",
        "--catalog-source",
        help="Catalog source: builtin, a local JSON file path, or a JSON URL",
    ),
):
    """Show details for one public skill catalog entry."""
    from kabot.cli.skill_catalog import resolve_catalog_skill

    try:
        entry = resolve_catalog_skill(slug, source=catalog_source)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if not entry:
        console.print(f"[yellow]Catalog skill not found: {slug}[/yellow]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]{entry['slug']}[/bold cyan]")
    console.print(entry["description"])
    homepage = str(entry.get("homepage") or "").strip()
    if homepage:
        console.print(f"Homepage: {homepage}")
    tags = entry.get("tags") or []
    if tags:
        console.print(f"Tags: {', '.join(str(tag) for tag in tags)}")
    install = entry.get("install") or {}
    if "git" in install:
        console.print(f"Install git: {install['git']}")
    if "url" in install:
        console.print(f"Install url: {install['url']}")
    if "subdir" in install:
        console.print(f"Subdir: {install['subdir']}")
    if "path" in install:
        console.print(f"Install path: {install['path']}")

def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    created = ensure_workspace_templates(workspace)
    for file_path in created:
        relative = file_path.relative_to(workspace)
        console.print(f"  [dim]Created {relative}[/dim]")
