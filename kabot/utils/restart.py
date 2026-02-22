import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


class RestartManager:
    """
    Manages state preservation across bot restarts.
    """

    def __init__(self, file_path: str = "RESTART_PENDING.json"):
        self.file_path = Path(file_path)

    def schedule_restart(self, chat_id: str, channel: str, message: str) -> None:
        """
        Saves restart context to a JSON file.

        Args:
            chat_id: The ID of the chat where the restart was triggered.
            channel: The communication channel (e.g., 'telegram', 'discord').
            message: The message to send after restart.
        """
        data = {
            "chat_id": chat_id,
            "channel": channel,
            "message": message,
            "timestamp": time.time()
        }

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Restart scheduled. Context saved to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to save restart context: {e}")
            raise e

    def check_and_recover(self) -> Optional[Dict[str, Any]]:
        """
        Checks for a pending restart file, reads it, and deletes it.

        Returns:
            Dict containing restart context if found, None otherwise.
        """
        if not self.file_path.exists():
            return None

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Delete the file after reading to prevent loops
            self.file_path.unlink()
            logger.info(f"Restart context recovered from {self.file_path}")
            return data

        except Exception as e:
            logger.error(f"Failed to recover restart context: {e}")
            return None
