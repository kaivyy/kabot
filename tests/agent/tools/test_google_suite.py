from types import SimpleNamespace

import pytest

from kabot.agent.tools.google_suite import (
    GmailTool,
    GoogleCalendarTool,
    GoogleDocsTool,
    GoogleDriveTool,
)


@pytest.mark.asyncio
async def test_gmail_search_emails_formats_summary():
    tool = GmailTool()
    tool._client = SimpleNamespace(
        search_emails=lambda query, max_results: [
            {
                "id": "m1",
                "snippet": "Quarterly report attached",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Q1 Report"},
                        {"name": "From", "value": "ceo@example.com"},
                    ]
                },
            }
        ]
    )

    result = await tool.execute(action="search_emails", query="is:unread", max_results=5)
    assert "[m1]" in result
    assert "Q1 Report" in result
    assert "ceo@example.com" in result


@pytest.mark.asyncio
async def test_gmail_send_email_requires_required_fields():
    tool = GmailTool()
    tool._client = SimpleNamespace(send_email=lambda **kwargs: {"id": "x"})

    result = await tool.execute(action="send_email", to="a@example.com", subject="")
    assert "required" in result.lower()


@pytest.mark.asyncio
async def test_gmail_send_email_success_message():
    tool = GmailTool()
    tool._client = SimpleNamespace(send_email=lambda **kwargs: {"id": "sent-1"})

    result = await tool.execute(
        action="send_email",
        to="a@example.com",
        subject="Hello",
        body_text="Body",
    )
    assert "Email sent successfully" in result
    assert "sent-1" in result


@pytest.mark.asyncio
async def test_gmail_save_draft_success_message():
    tool = GmailTool()
    tool._client = SimpleNamespace(send_email=lambda **kwargs: {"id": "draft-1"})

    result = await tool.execute(
        action="save_draft",
        to="a@example.com",
        subject="Draft",
        body_text="Body",
    )
    assert "Draft saved successfully" in result
    assert "draft-1" in result


@pytest.mark.asyncio
async def test_google_calendar_create_event_validates_required_fields():
    tool = GoogleCalendarTool()
    tool._client = SimpleNamespace(create_event=lambda **kwargs: {"htmlLink": "x"})

    result = await tool.execute(action="create_event", summary="Standup", start_time_iso="2026-03-06T09:00:00Z")
    assert "required" in result.lower()


@pytest.mark.asyncio
async def test_google_calendar_create_event_success():
    tool = GoogleCalendarTool()
    tool._client = SimpleNamespace(create_event=lambda **kwargs: {"htmlLink": "https://calendar.google.com/event/123"})

    result = await tool.execute(
        action="create_event",
        summary="Standup",
        start_time_iso="2026-03-06T09:00:00Z",
        end_time_iso="2026-03-06T09:30:00Z",
    )
    assert "Event created" in result
    assert "calendar.google.com" in result


@pytest.mark.asyncio
async def test_google_calendar_list_events_empty_result():
    tool = GoogleCalendarTool()
    tool._client = SimpleNamespace(list_events=lambda **kwargs: [])

    result = await tool.execute(action="list_events", max_results=3)
    assert result == "No events found."


@pytest.mark.asyncio
async def test_google_drive_search_files_formats_rows():
    tool = GoogleDriveTool()
    tool._client = SimpleNamespace(
        search_files=lambda **kwargs: [
            {"id": "f1", "name": "Budget.xlsx", "webViewLink": "https://drive.google.com/file/f1"}
        ]
    )

    result = await tool.execute(action="search_files", query="name contains 'Budget'")
    assert "[f1]" in result
    assert "Budget.xlsx" in result
    assert "drive.google.com" in result


@pytest.mark.asyncio
async def test_google_drive_upload_text_requires_name_and_content():
    tool = GoogleDriveTool()
    tool._client = SimpleNamespace(upload_text_file=lambda *args, **kwargs: {"id": "x"})

    result = await tool.execute(action="upload_text", name="report.md")
    assert "required" in result.lower()


@pytest.mark.asyncio
async def test_google_docs_create_and_append_flows():
    tool = GoogleDocsTool()
    tool._client = SimpleNamespace(
        create_document=lambda title: {"documentId": "doc-1", "webViewLink": "https://docs.google.com/document/d/doc-1/edit"},
        append_text=lambda doc_id, text: True,
        read_document=lambda doc_id: "Existing content",
    )

    created = await tool.execute(action="create_document", title="Weekly Notes")
    appended = await tool.execute(action="append_text", document_id="doc-1", text="Follow up item")
    read_back = await tool.execute(action="read_document", document_id="doc-1")

    assert "Document created!" in created
    assert "doc-1" in created
    assert appended == "Text appended successfully."
    assert read_back == "Existing content"
