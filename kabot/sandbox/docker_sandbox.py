"""Docker-backed sandbox execution helper."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

try:
    import docker  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency
    docker = None  # type: ignore[assignment]


class DockerSandbox:
    """Execute shell commands in an isolated Docker container."""

    def __init__(
        self,
        image: str,
        *,
        mode: str = "off",
        workspace: str | Path | None = None,
        workspace_access: str = "rw",
        network_disabled: bool = False,
    ):
        self.image = image
        self.mode = mode
        self.workspace = Path(workspace).expanduser().resolve() if workspace else None
        self.workspace_access = workspace_access
        self.network_disabled = network_disabled
        self._client: Any | None = None
        self._container: Any | None = None

    @property
    def is_active(self) -> bool:
        return self.mode in ("all", "non-main")

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if docker is None:
            raise RuntimeError("docker SDK not available")
        self._client = docker.from_env()
        return self._client

    def _create_container(self):
        if self._container is not None:
            return self._container

        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "image": self.image,
            "command": "sleep infinity",
            "detach": True,
            "tty": True,
            "stdin_open": False,
        }
        if self.workspace:
            kwargs["working_dir"] = "/workspace"
            kwargs["volumes"] = {
                str(self.workspace): {
                    "bind": "/workspace",
                    "mode": self.workspace_access,
                }
            }
        if self.network_disabled:
            kwargs["network_disabled"] = True

        self._container = client.containers.run(**kwargs)
        return self._container

    async def _run_in_container(self, command: str) -> str:
        """Run command in sandbox container and return stdout/stderr text."""
        container = self._create_container()

        def _run():
            return container.exec_run(command)

        exit_code, output = await asyncio.to_thread(_run)
        text = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
        if exit_code != 0:
            raise RuntimeError(f"sandbox command failed ({exit_code}): {text.strip()}")
        return text

    async def exec_command(self, command: str) -> str | None:
        """Execute a command in sandbox and return decoded output."""
        if not self.is_active:
            return None
        return await self._run_in_container(command)

    async def close(self) -> None:
        """Stop and remove container resources."""
        container = self._container
        self._container = None
        if container is not None:
            await asyncio.to_thread(container.remove, force=True)

        client = self._client
        self._client = None
        if client is not None:
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
