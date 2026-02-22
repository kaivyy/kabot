import base64
from email.message import EmailMessage
from typing import Any

from googleapiclient.discovery import build
from loguru import logger

from kabot.auth.google_auth import GoogleAuthManager


class GmailClient:
    """Client for native Gmail API interactions."""

    def __init__(self, auth_manager: GoogleAuthManager | None = None):
        if not auth_manager:
            auth_manager = GoogleAuthManager()
            
        creds = auth_manager.get_credentials()
        self.service = build("gmail", "v1", credentials=creds)

    def search_emails(self, query: str = "is:inbox", max_results: int = 10) -> list[dict[str, Any]]:
        """Search for emails matching a specific query."""
        logger.info(f"Querying native Gmail API: '{query}' (max: {max_results})")
        try:
            results = self.service.users().messages().list(
                userId="me", q=query, maxResults=max_results
            ).execute()
            messages = results.get("messages", [])
            
            # Fetch details for each message
            full_messages = []
            for msg in messages:
                msg_full = self.service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata"
                ).execute()
                full_messages.append(msg_full)

            return full_messages
        except Exception as e:
            logger.error(f"Failed to fetch Gmail items: {e}")
            return []

    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        is_draft: bool = False
    ) -> dict[str, Any] | None:
        """Send an email natively using the Gmail API."""
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)

        if body_html:
            message.add_alternative(body_html, subtype="html")

        # Encoded string required by Gmail API
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        try:
            if is_draft:
                logger.info(f"Saving native Gmail Draft to {to}...")
                draft = self.service.users().drafts().create(
                    userId="me", body={"message": create_message}
                ).execute()
                logger.info(f"Draft saved successfully with ID: {draft.get('id')}")
                return draft
            else:
                logger.info(f"Sending native Gmail to {to}...")
                sent_message = self.service.users().messages().send(
                    userId="me", body=create_message
                ).execute()
                logger.info(f"Email sent successfully with ID: {sent_message.get('id')}")
                return sent_message

        except Exception as e:
            logger.error(f"Failed to send/save Gmail: {e}")
            return None
