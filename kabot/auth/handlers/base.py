from abc import ABC, abstractmethod
from typing import Dict, Any

class AuthHandler(ABC):
    """
    Abstract base class for all authentication handlers.
    Each provider (OpenAI, Anthropic, etc.) must implement this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the display name of the provider."""
        pass

    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """
        Execute the authentication flow (interactive).

        Returns:
            Dict containing the configuration fragment to be merged into the main config.
            Example: {'providers': {'openai': {'api_key': 'sk-...'}}}
        """
        pass

    def validate(self, credentials: Dict[str, Any]) -> bool:
        """
        Optional: Validate the credentials (e.g. by making a test API call).
        Returns True if valid, False otherwise.
        """
        return True
