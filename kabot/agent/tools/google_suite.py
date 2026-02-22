from typing import Any, Optional

from loguru import logger

from kabot.agent.tools.base import Tool
from kabot.integrations.gmail import GmailClient
from kabot.integrations.google_calendar import GoogleCalendarClient


class GoogleCalendarTool(Tool):
    """Tool for native Google Calendar interactions."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> GoogleCalendarClient:
        # Lazy initialization
        if not self._client:
            self._client = GoogleCalendarClient()
        return self._client

    @property
    def name(self) -> str:
        return "google_calendar"

    @property
    def description(self) -> str:
        return (
            "Interact natively with Google Calendar. "
            "Supported actions: list_events, create_event."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: list_events, create_event.",
                    "enum": ["list_events", "create_event"]
                },
                "summary": {
                    "type": "string",
                    "description": "Title of the newly created event (required for create_event)."
                },
                "start_time_iso": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g. 2026-02-23T15:00:00Z) (required for create_event)."
                },
                "end_time_iso": {
                    "type": "string",
                    "description": "End time in ISO 8601 format (required for create_event)."
                },
                "time_min": {
                    "type": "string",
                    "description": "Lower bound time (ISO 8601) to filter events (optional for list_events)."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of events to load (default: 10)."
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, **kwargs) -> Any:
        try:
            if action == "list_events":
                max_results = kwargs.get("max_results", 10)
                time_min = kwargs.get("time_min")
                events = self.client.list_events(max_results=max_results, time_min=time_min)
                return events if events else "No events found."
            
            elif action == "create_event":
                summary = kwargs.get("summary")
                start = kwargs.get("start_time_iso")
                end = kwargs.get("end_time_iso")
                
                if not summary or not start or not end:
                    return "Error: 'summary', 'start_time_iso', and 'end_time_iso' are required to create an event."
                
                result = self.client.create_event(
                    summary=summary,
                    start_time_iso=start,
                    end_time_iso=end,
                    description=kwargs.get("description", "")
                )
                if result:
                    return f"Event created: {result.get('htmlLink')}"
                return "Failed to create event."
                
            return f"Unknown calendar action: {action}"
        except Exception as e:
            logger.error(f"GoogleCalendarTool failed: {e}")
            return f"Action failed: {str(e)}"


class GmailTool(Tool):
    """Tool for native Gmail interactions."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> GmailClient:
        # Lazy initialization
        if not self._client:
            self._client = GmailClient()
        return self._client

    @property
    def name(self) -> str:
        return "gmail"

    @property
    def description(self) -> str:
        return (
            "Interact natively with Gmail. "
            "Supported actions: search_emails, send_email, save_draft."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: search_emails, send_email, save_draft.",
                    "enum": ["search_emails", "send_email", "save_draft"]
                },
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g. 'is:unread', 'from:boss@corp.com') (used in search_emails)."
                },
                "to": {
                    "type": "string",
                    "description": "Recipient email address (required for send_email & save_draft)."
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject (required for send_email & save_draft)."
                },
                "body_text": {
                    "type": "string",
                    "description": "Email plain text body (required for send_email & save_draft)."
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, **kwargs) -> Any:
        try:
            if action == "search_emails":
                query = kwargs.get("query", "is:inbox")
                results = self.client.search_emails(query=query, max_results=kwargs.get("max_results", 10))
                # Simplify output so LLM doesn't choke on massive JSON payloads
                summaries = []
                for msg in results:
                    headers = msg.get("payload", {}).get("headers", [])
                    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
                    sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
                    summaries.append(f"[{msg['id']}] From: {sender} | Subject: {subject} | Snippet: {msg.get('snippet')}")
                return "\n".join(summaries) if summaries else "No emails found matching query."
            
            elif action in ["send_email", "save_draft"]:
                to = kwargs.get("to")
                subject = kwargs.get("subject")
                body = kwargs.get("body_text")
                
                if not to or not subject or not body:
                    return "Error: 'to', 'subject', and 'body_text' are required."
                
                is_draft = action == "save_draft"
                result = self.client.send_email(
                    to=to,
                    subject=subject,
                    body_text=body,
                    is_draft=is_draft
                )
                if result:
                    status = "Draft saved" if is_draft else "Email sent"
                    return f"{status} successfully with ID: {result.get('id')}"
                return f"Failed to {'save draft' if is_draft else 'send email'}."
                
            return f"Unknown gmail action: {action}"
        except Exception as e:
            logger.error(f"GmailTool failed: {e}")
            return f"Action failed: {str(e)}"
