# kabot/agent/mode_manager.py
import json
from pathlib import Path


class ModeManager:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._save({"users": {}})

    def _load(self) -> dict:
        with open(self.config_path) as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def set_mode(self, user_id: str, mode: str) -> None:
        if mode not in ["single", "multi"]:
            raise ValueError(f"Invalid mode: {mode}")

        data = self._load()
        if user_id not in data["users"]:
            data["users"][user_id] = {}
        data["users"][user_id]["mode"] = mode
        self._save(data)

    def get_mode(self, user_id: str) -> str:
        data = self._load()
        return data["users"].get(user_id, {}).get("mode", "single")

    def set_custom_config(self, user_id: str, config: dict) -> None:
        data = self._load()
        if user_id not in data["users"]:
            data["users"][user_id] = {}
        data["users"][user_id]["custom_config"] = config
        self._save(data)

    def get_custom_config(self, user_id: str) -> dict:
        data = self._load()
        return data["users"].get(user_id, {}).get("custom_config", {})
