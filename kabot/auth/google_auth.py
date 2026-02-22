from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

# Essential scopes for full integrations. Read & write for Mail & Calendar, Drive, and Docs.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents"
]


class GoogleAuthManager:
    """Manages the Google OAuth2 flow natively without external CLI."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".kabot"

        # Path to user-provided credentials (downloaded from GCP Console)
        self.credentials_path = self.workspace / "google_credentials.json"

        # Path where the resulting OAuth token is stored for reuse
        self.token_path = self.workspace / "google_token.json"

    def get_credentials(self) -> Credentials:
        """
        Get valid user credentials from storage.
        If nothing exists or token expired, trigger the OAuth flow.
        """
        creds = None

        # 1. Check if token already exists
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load existing google token: {e}")
                creds = None

        # 2. If no valid credentials, run login flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired Google OAuth token...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Failed to refresh token, prompting re-auth: {e}")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    msg = (
                        f"Missing Google OAuth Credentials at {self.credentials_path}.\n"
                        "Please download an OAuth 2.0 Client ID (Desktop type) from "
                        "Google Cloud Console and save it to that location."
                    )
                    logger.error(msg)
                    raise FileNotFoundError(msg)

                logger.info("Initiating new Google OAuth login flow...")
                # Run the native auth server on localhost
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the new token for the next run
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
                logger.info(f"Saved new Google OAuth token to {self.token_path}")

        return creds
