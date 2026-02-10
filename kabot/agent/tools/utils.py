"""Utility tools for AutoPlanner."""

from pathlib import Path
from kabot.agent.tools.base import Tool


class CountLinesTool(Tool):
    """Tool untuk menghitung baris dalam text atau file."""

    name = "count_lines"
    description = "Count lines in text or file content"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text content to count lines"
            },
            "path": {
                "type": "string",
                "description": "Path to file to count lines"
            }
        },
        "required": []
    }

    async def execute(self, text: str = None, path: str = None) -> str:
        """Execute line counting."""
        if path:
            content = Path(path).read_text()
            lines = content.split('\n')
            return f"File {path} has {len(lines)} lines"
        elif text:
            lines = text.split('\n')
            return f"Text has {len(lines)} lines"
        else:
            return "Error: No text or path provided"


class EchoTool(Tool):
    """Tool untuk echo message."""

    name = "echo"
    description = "Echo a message back"
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to echo"
            }
        },
        "required": ["message"]
    }

    async def execute(self, message: str) -> str:
        """Execute echo."""
        return message
