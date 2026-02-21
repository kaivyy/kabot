"""Configuration loading utilities."""

import json
import os
import shutil
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
            data = _migrate_config(data)
            return Config.model_validate(convert_keys(data))
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
                # Create backup like OpenClaw
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
    return data


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


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
