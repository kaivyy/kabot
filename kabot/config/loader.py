"""Configuration loading utilities."""

import json
import os
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from kabot.config.schema import Config
from kabot.utils.pid_lock import PIDLock


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".kabot" / "config.json"


def get_data_dir() -> Path:
    """Get the kabot data directory (legacy support)."""
    from kabot.utils.helpers import get_data_path
    return get_data_path()


def get_global_data_dir() -> Path:
    """Get the global kabot data directory (for shared creds/db)."""
    return get_data_dir()


def get_credentials_dir() -> Path:
    """Get the global credentials directory (Token Sink)."""
    path = get_global_data_dir() / "credentials"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_agent_dir(agent_id: str = "main") -> Path:
    """Get the dedicated directory for a specific agent."""
    path = get_global_data_dir() / "agents" / agent_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Loaded configuration object.
    """
    path = config_path or get_config_path()

    if path.exists():
        try:
            # Use utf-8-sig to tolerate BOM-prefixed JSON written by some tools.
            with open(path, encoding="utf-8-sig") as f:
                data = json.load(f)
            original_data = deepcopy(data)
            migrated_data = _migrate_config(data)
            if migrated_data != original_data:
                backup_path = _persist_migrated_config(path, migrated_data)
                print(
                    "Info: Migrated legacy config keys to canonical format "
                    f"(backup: {backup_path})."
                )
            return Config.model_validate(convert_keys(migrated_data))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")

    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file with PID-based locking and atomic writes.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to camelCase format
    data = config.model_dump()
    data = convert_to_camel(data)

    # Use PIDLock for multi-process safety with stale lock recovery
    with PIDLock(path):
        # Write to temp file first for atomic replacement
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)

        # Atomic rename (replace existing if possible)
        if os.name == 'nt': # Windows
            if path.exists():
                # Create backup like Kabot
                backup_path = path.with_suffix(".json.bak")
                try:
                    if backup_path.exists():
                        os.remove(backup_path)
                    os.rename(path, backup_path)
                except Exception:
                    pass
            # Move temp to final
            if path.exists():
                os.remove(path)
            os.rename(temp_path, path)
        else: # Unix
            if path.exists():
                shutil.copy2(path, path.with_suffix(".json.bak"))
            os.replace(temp_path, path)


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace -> tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")

    # Legacy top-level "threads" config -> integrations.meta
    threads_cfg = data.get("threads")
    if isinstance(threads_cfg, dict):
        integrations = data.get("integrations")
        if not isinstance(integrations, dict):
            integrations = {}
            data["integrations"] = integrations

        meta_cfg = integrations.get("meta")
        if not isinstance(meta_cfg, dict):
            meta_cfg = {}
            integrations["meta"] = meta_cfg

        def read_value(payload: dict[str, Any], *keys: str) -> Any:
            for key in keys:
                if key not in payload:
                    continue
                value = payload.get(key)
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        return value
                    continue
                if value is not None:
                    return value
            return None

        def set_if_missing(keys: tuple[str, ...], value: Any) -> None:
            if value is None:
                return
            if read_value(meta_cfg, *keys) is not None:
                return
            meta_cfg[keys[0]] = value

        set_if_missing(
            ("threads_user_id", "threadsUserId"),
            read_value(threads_cfg, "threads_user_id", "threadsUserId", "user_id", "userId"),
        )
        set_if_missing(
            ("instagram_user_id", "instagramUserId"),
            read_value(threads_cfg, "instagram_user_id", "instagramUserId"),
        )
        set_if_missing(
            ("access_token", "accessToken"),
            read_value(threads_cfg, "access_token", "accessToken", "token"),
        )
        set_if_missing(
            ("access_token_env", "accessTokenEnv"),
            read_value(threads_cfg, "access_token_env", "accessTokenEnv"),
        )

        enabled_value = read_value(threads_cfg, "enabled")
        if read_value(meta_cfg, "enabled") is None:
            if enabled_value is None:
                has_credentials = (
                    read_value(
                        meta_cfg,
                        "access_token",
                        "accessToken",
                        "access_token_env",
                        "accessTokenEnv",
                        "threads_user_id",
                        "threadsUserId",
                    )
                    is not None
                )
                if has_credentials:
                    meta_cfg["enabled"] = True
            else:
                meta_cfg["enabled"] = bool(enabled_value)

        # Prevent validation failure due extra field on current schema.
        data.pop("threads", None)

    # Canonicalize skills structure (entries/load/install).
    skills_cfg = data.get("skills")
    from kabot.config.skills_settings import normalize_skills_settings

    normalized_skills = normalize_skills_settings(skills_cfg if isinstance(skills_cfg, dict) else {})
    data["skills"] = convert_to_camel(normalized_skills)

    # Ensure tools.exec.policyPreset exists with compatibility-aware defaults.
    tools_cfg = data.get("tools")
    if isinstance(tools_cfg, dict):
        exec_cfg = tools_cfg.get("exec")
        if isinstance(exec_cfg, dict):
            if "policyPreset" not in exec_cfg and "policy_preset" not in exec_cfg:
                auto_approve = bool(exec_cfg.get("autoApprove", exec_cfg.get("auto_approve", False)))
                restrict_ws = bool(
                    tools_cfg.get("restrictToWorkspace", tools_cfg.get("restrict_to_workspace", False))
                )
                if auto_approve:
                    exec_cfg["policyPreset"] = "compat"
                elif restrict_ws:
                    exec_cfg["policyPreset"] = "strict"
                else:
                    exec_cfg["policyPreset"] = "balanced"
                tools_cfg["exec"] = exec_cfg

    # Inject canonical runtime resilience/performance sections if missing.
    runtime_cfg = data.get("runtime")
    if not isinstance(runtime_cfg, dict):
        runtime_cfg = {}
        data["runtime"] = runtime_cfg

    resilience_defaults = {
        "enabled": True,
        "dedupeToolCalls": True,
        "maxModelAttemptsPerTurn": 4,
        "maxToolRetryPerTurn": 1,
        "strictErrorClassification": True,
        "preventModelChainMutation": True,
        "idempotencyTtlSeconds": 600,
    }
    performance_defaults = {
        "fastFirstResponse": True,
        "deferMemoryWarmup": True,
        "embedWarmupTimeoutMs": 1200,
        "maxContextBuildMs": 500,
        "maxFirstResponseMsSoft": 4000,
    }
    autopilot_defaults = {
        "enabled": True,
        "prompt": (
            "Autopilot patrol: review recent context, pending schedules, and recent failures. "
            "Identify one highest bottleneck that blocks user outcomes. "
            "Execute at most one safe action to reduce it; otherwise respond with 'no_action'."
        ),
        "maxActionsPerBeat": 1,
    }
    observability_defaults = {
        "enabled": True,
        "emitStructuredEvents": True,
        "sampleRate": 1.0,
        "redactSecrets": True,
    }
    quota_defaults = {
        "enabled": False,
        "maxCostPerDayUsd": 0.0,
        "maxTokensPerHour": 0,
        "enforcementMode": "warn",
    }

    resilience_cfg = runtime_cfg.get("resilience")
    if not isinstance(resilience_cfg, dict):
        resilience_cfg = {}
    for key, default_val in resilience_defaults.items():
        if key not in resilience_cfg:
            resilience_cfg[key] = default_val
    runtime_cfg["resilience"] = resilience_cfg

    performance_cfg = runtime_cfg.get("performance")
    if not isinstance(performance_cfg, dict):
        performance_cfg = {}
    for key, default_val in performance_defaults.items():
        if key not in performance_cfg:
            performance_cfg[key] = default_val
    runtime_cfg["performance"] = performance_cfg

    autopilot_cfg = runtime_cfg.get("autopilot")
    if not isinstance(autopilot_cfg, dict):
        autopilot_cfg = {}
    for key, default_val in autopilot_defaults.items():
        if key not in autopilot_cfg:
            autopilot_cfg[key] = default_val
    runtime_cfg["autopilot"] = autopilot_cfg

    observability_cfg = runtime_cfg.get("observability")
    if not isinstance(observability_cfg, dict):
        observability_cfg = {}
    for key, default_val in observability_defaults.items():
        if key not in observability_cfg:
            observability_cfg[key] = default_val
    runtime_cfg["observability"] = observability_cfg

    quota_cfg = runtime_cfg.get("quotas")
    if not isinstance(quota_cfg, dict):
        quota_cfg = {}
    for key, default_val in quota_defaults.items():
        if key not in quota_cfg:
            quota_cfg[key] = default_val
    runtime_cfg["quotas"] = quota_cfg

    # Security trust-mode defaults.
    security_cfg = data.get("security")
    if not isinstance(security_cfg, dict):
        security_cfg = {}
        data["security"] = security_cfg
    trust_mode_cfg = security_cfg.get("trustMode")
    if not isinstance(trust_mode_cfg, dict):
        trust_mode_cfg = {}
    if "enabled" not in trust_mode_cfg:
        trust_mode_cfg["enabled"] = False
    if "verifySkillManifest" not in trust_mode_cfg:
        trust_mode_cfg["verifySkillManifest"] = False
    if "allowedSigners" not in trust_mode_cfg:
        trust_mode_cfg["allowedSigners"] = []
    security_cfg["trustMode"] = trust_mode_cfg
    return data


def _persist_migrated_config(path: Path, migrated_data: dict) -> Path:
    """Write migrated config and keep a timestamped pre-migration backup."""
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{path.stem}.{ts}.pre-migration{path.suffix}"
    if path.exists():
        shutil.copy2(path, backup_path)

    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(migrated_data, f, indent=2)
    os.replace(temp_path, path)
    return backup_path


def convert_keys(data: Any) -> Any:
    """Convert camelCase keys to snake_case for Pydantic."""
    if isinstance(data, dict):
        return {camel_to_snake(k): convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item) for item in data]
    return data


def convert_to_camel(data: Any) -> Any:
    """Convert snake_case keys to camelCase."""
    if isinstance(data, dict):
        return {snake_to_camel(k): convert_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data


def _is_constant_style_key(name: str) -> bool:
    """Return True for constant-style keys like ENV_VAR names."""
    if not name:
        return False
    return all(ch.isupper() or ch.isdigit() or ch == "_" for ch in name)


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    # Preserve ENV-like constant keys (e.g. OPENAI_API_KEY).
    if _is_constant_style_key(name):
        return name
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    # Preserve ENV-like constant keys (e.g. OPENAI_API_KEY).
    if _is_constant_style_key(name):
        return name
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


