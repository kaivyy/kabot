from typing import Any

from googleapiclient.discovery import build
from loguru import logger

from kabot.auth.google_auth import GoogleAuthManager


class GoogleDocsClient:
    """Client for native Google Docs API interactions."""

    def __init__(self, auth_manager: GoogleAuthManager | None = None):
        if not auth_manager:
            auth_manager = GoogleAuthManager()

        creds = auth_manager.get_credentials()
        self.service = build("docs", "v1", credentials=creds)

    def create_document(self, title: str) -> dict[str, Any] | None:
        """Create a blank Google Doc with the given title."""
        logger.info(f"Creating new Google Doc: '{title}'...")
        try:
            document = self.service.documents().create(body={"title": title}).execute()
            link = f"https://docs.google.com/document/d/{document.get('documentId')}/edit"
            logger.info(f"Document created successfully: {link}")
            document["webViewLink"] = link
            return document
        except Exception as e:
            logger.error(f"Failed to create Google Doc: {e}")
            return None

    def read_document(self, document_id: str) -> str:
        """Read all text content from a Google Doc by ID."""
        logger.info(f"Reading Google Doc ID: '{document_id}'...")
        try:
            document = self.service.documents().get(documentId=document_id).execute()
            text_content = ""

            # Very basic extraction: traverse structural elements
            for element in document.get("body", {}).get("content", []):
                if "paragraph" in element:
                    for p_element in element["paragraph"].get("elements", []):
                        if "textRun" in p_element:
                            text_content += p_element["textRun"].get("content", "")

            return text_content
        except Exception as e:
            logger.error(f"Failed to read Google Doc: {e}")
            return f"Error reading document: {str(e)}"

    def append_text(self, document_id: str, text: str) -> bool:
        """Append text to the VERY END of an existing Google Doc."""
        logger.info(f"Appending text to Google Doc ID: '{document_id}'...")
        try:
            # First, fetch doc to find the end index
            document = self.service.documents().get(documentId=document_id).execute()
            # The body content always ends with a newline, so we insert right before it
            end_index = 1
            content_list = document.get("body", {}).get("content", [])
            if content_list:
                end_index = content_list[-1].get("endIndex", 1) - 1

            requests = [
                {
                    "insertText": {
                        "location": {
                            "index": max(1, end_index)
                        },
                        "text": text + "\n"
                    }
                }
            ]
            self.service.documents().batchUpdate(
                documentId=document_id, body={"requests": requests}
            ).execute()
            logger.info("Successfully appended text to Google Doc.")
            return True
        except Exception as e:
            logger.error(f"Failed to append text to Google Doc: {e}")
            return False
