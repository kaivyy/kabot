import json
from pathlib import Path
from typing import Any

class AgentRegistry:
    def __init__(self, registry_path: Path):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save({"agents": {}})

    def _load(self) -> dict[str, Any]:
        with open(self.registry_path) as f:
            return json.load(f)

    def _save(self, data: dict[str, Any]) -> None:
        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, agent_id: str, name: str, model: str, workspace: str) -> None:
        data = self._load()
        data["agents"][agent_id] = {
            "id": agent_id,
            "name": name,
            "model": model,
            "workspace": workspace
        }
        self._save(data)

    def get(self, agent_id: str) -> dict[str, Any] | None:
        data = self._load()
        return data["agents"].get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        data = self._load()
        return list(data["agents"].values())
