import datetime
from typing import Any

from googleapiclient.discovery import build
from loguru import logger

from kabot.auth.google_auth import GoogleAuthManager


class GoogleCalendarClient:
    """Client for native Google Calendar API interactions."""

    def __init__(self, auth_manager: GoogleAuthManager | None = None):
        if not auth_manager:
            auth_manager = GoogleAuthManager()

        creds = auth_manager.get_credentials()
        self.service = build("calendar", "v3", credentials=creds)

    def list_events(self, calendar_id: str = "primary", max_results: int = 10, time_min: str | None = None) -> list[dict[str, Any]]:
        """List upcoming events from a specific calendar."""
        if not time_min:
            # Default to now
            time_min = datetime.datetime.utcnow().isoformat() + "Z"

        logger.info(f"Fetching up to {max_results} events from Google Calendar '{calendar_id}'...")
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            events = events_result.get("items", [])
            return events
        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return []

    def create_event(
        self,
        summary: str,
        start_time_iso: str,
        end_time_iso: str,
        description: str = "",
        calendar_id: str = "primary",
        color_id: str | None = None
    ) -> dict[str, Any] | None:
        """Create a new event in Google Calendar."""
        event: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time_iso,
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time_iso,
                "timeZone": "UTC",
            },
        }

        if color_id:
            event["colorId"] = str(color_id)

        logger.info(f"Creating native Google Calendar Event: '{summary}'...")
        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id, body=event
            ).execute()
            logger.info(f"Event created successfully: {created_event.get('htmlLink')}")
            return created_event
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return None
