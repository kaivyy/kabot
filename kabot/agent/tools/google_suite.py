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

class GoogleDriveTool(Tool):
    """Tool for native Google Drive interactions."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if not self._client:
            from kabot.integrations.google_drive import GoogleDriveClient
            self._client = GoogleDriveClient()
        return self._client

    @property
    def name(self) -> str:
        return "google_drive"

    @property
    def description(self) -> str:
        return (
            "Interact natively with Google Drive. "
            "Supported actions: search_files, upload_text."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: search_files, upload_text.",
                    "enum": ["search_files", "upload_text"]
                },
                "query": {
                    "type": "string",
                    "description": "Google Drive search query (used in search_files)."
                },
                "name": {
                    "type": "string",
                    "description": "File name for upload (required for upload_text)."
                },
                "content": {
                    "type": "string",
                    "description": "Text/Markdown content to upload (required for upload_text)."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of files to return (default: 10)."
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, **kwargs) -> Any:
        try:
            if action == "search_files":
                query = kwargs.get("query", "trashed = false")
                max_results = kwargs.get("max_results", 10)
                files = self.client.search_files(query=query, max_results=max_results)
                
                if not files:
                    return "No files found matching query."
                    
                summaries = []
                for f in files:
                    summaries.append(f"[{f['id']}] {f['name']} (URL: {f.get('webViewLink')})")
                return "\n".join(summaries)
            
            elif action == "upload_text":
                name = kwargs.get("name")
                content = kwargs.get("content")
                if not name or not content:
                    return "Error: 'name' and 'content' required for upload_text."
                    
                result = self.client.upload_text_file(name, content)
                if result:
                    return f"File '{name}' uploaded successfully. Link: {result.get('webViewLink')}"
                return "Failed to upload file."
                
            return f"Unknown drive action: {action}"
        except Exception as e:
            logger.error(f"GoogleDriveTool failed: {e}")
            return f"Action failed: {str(e)}"

class GoogleDocsTool(Tool):
    """Tool for native Google Docs interactions."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if not self._client:
            from kabot.integrations.google_docs import GoogleDocsClient
            self._client = GoogleDocsClient()
        return self._client

    @property
    def name(self) -> str:
        return "google_docs"

    @property
    def description(self) -> str:
        return (
            "Interact natively with Google Docs. "
            "Supported actions: create_document, read_document, append_text."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: create_document, read_document, append_text.",
                    "enum": ["create_document", "read_document", "append_text"]
                },
                "title": {
                    "type": "string",
                    "description": "Title of the new document (required for create_document)."
                },
                "document_id": {
                    "type": "string",
                    "description": "ID of the Google Doc (required for read_document and append_text)."
                },
                "text": {
                    "type": "string",
                    "description": "Text to append (required for append_text)."
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, **kwargs) -> Any:
        try:
            if action == "create_document":
                title = kwargs.get("title")
                if not title:
                    return "Error: 'title' is required for create_document."
                result = self.client.create_document(title)
                if result:
                    return f"Document created! ID: {result.get('documentId')} | Link: {result.get('webViewLink')}"
                return "Failed to create document."
                
            elif action == "read_document":
                doc_id = kwargs.get("document_id")
                if not doc_id:
                    return "Error: 'document_id' is required for read_document."
                return self.client.read_document(doc_id)
                
            elif action == "append_text":
                doc_id = kwargs.get("document_id")
                text = kwargs.get("text")
                if not doc_id or not text:
                    return "Error: 'document_id' and 'text' required for append_text."
                success = self.client.append_text(doc_id, text)
                return "Text appended successfully." if success else "Failed to append text."
                
            return f"Unknown docs action: {action}"
        except Exception as e:
            logger.error(f"GoogleDocsTool failed: {e}")
            return f"Action failed: {str(e)}"
