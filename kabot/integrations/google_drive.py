import io
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from loguru import logger

from kabot.auth.google_auth import GoogleAuthManager


class GoogleDriveClient:
    """Client for native Google Drive API interactions."""

    def __init__(self, auth_manager: GoogleAuthManager | None = None):
        if not auth_manager:
            auth_manager = GoogleAuthManager()

        creds = auth_manager.get_credentials()
        self.service = build("drive", "v3", credentials=creds)

    def search_files(self, query: str = "", max_results: int = 10) -> list[dict[str, Any]]:
        """Search for files in Google Drive."""
        # Simple default query if none provided
        if not query:
            query = "trashed = false"

        logger.info(f"Querying native Google Drive API: '{query}' (max: {max_results})")
        try:
            results = self.service.files().list(
                q=query,
                pageSize=max_results,
                fields="nextPageToken, files(id, name, mimeType, webViewLink, createdTime)"
            ).execute()
            items = results.get("files", [])
            return items
        except Exception as e:
            logger.error(f"Failed to search Google Drive: {e}")
            return []

    def upload_text_file(self, name: str, content: str, mime_type: str = "text/plain") -> dict[str, Any] | None:
        """Upload a newly created text/markdown file directly to Google Drive."""
        file_metadata = {"name": name, "mimeType": mime_type}

        # Convert string to file-like stream
        media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype=mime_type, resumable=True)

        logger.info(f"Uploading file '{name}' to Google Drive...")
        try:
            file = self.service.files().create(
                body=file_metadata, media_body=media, fields="id, name, webViewLink"
            ).execute()
            logger.info(f"Successfully uploaded: {file.get('webViewLink')}")
            return file
        except Exception as e:
            logger.error(f"Failed to upload to Google Drive: {e}")
            return None
