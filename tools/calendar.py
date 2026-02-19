"""iCloud Calendar tools for MCP."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil import parser as dateparser


def _fmt_event(event: Any) -> dict:
    """Normalise a pyicloud calendar event to a plain dict."""
    data = event.get("fields", event) if hasattr(event, "get") else {}
    return {
        "uid": data.get("guid", ""),
        "title": data.get("title", "(no title)"),
        "start": str(data.get("startDate", "")),
        "end": str(data.get("endDate", "")),
        "location": data.get("location", ""),
        "description": data.get("description", ""),
        "calendar": data.get("pGuid", ""),
    }


def list_calendars(api: Any) -> list[dict]:
    """Return all calendars for the account."""
    calendars = api.calendar.calendars()
    return [
        {
            "uid": cal.get("guid", ""),
            "title": cal.get("title", ""),
            "color": cal.get("color", ""),
        }
        for cal in calendars
    ]


def list_events(
    api: Any,
    from_date: str | None = None,
    to_date: str | None = None,
    calendar_uid: str | None = None,
) -> list[dict]:
    """
    Return events in the given date range.

    Args:
        api: Authenticated PyiCloudService instance.
        from_date: ISO-8601 start date (default: today).
        to_date: ISO-8601 end date (default: 7 days from today).
        calendar_uid: Restrict to a specific calendar by UID.
    """
    now = datetime.now(tz=timezone.utc)
    start = dateparser.parse(from_date) if from_date else now
    end = dateparser.parse(to_date) if to_date else now + timedelta(days=7)

    events = api.calendar.events(start, end)
    result = [_fmt_event(e) for e in events]

    if calendar_uid:
        result = [e for e in result if e["calendar"] == calendar_uid]

    return result


def get_event(api: Any, event_uid: str) -> dict | None:
    """Return a single event by UID, or None if not found."""
    # Search in the next 90 days — widen if not found
    now = datetime.now(tz=timezone.utc)
    for window in [90, 365]:
        events = api.calendar.events(now - timedelta(days=window), now + timedelta(days=window))
        for e in events:
            data = e.get("fields", e) if hasattr(e, "get") else {}
            if data.get("guid") == event_uid:
                return _fmt_event(e)
    return None


def create_event(
    api: Any,
    title: str,
    start: str,
    end: str,
    calendar_uid: str | None = None,
    location: str = "",
    description: str = "",
) -> dict:
    """
    Create a new calendar event.

    Args:
        api: Authenticated PyiCloudService instance.
        title: Event title.
        start: ISO-8601 start datetime.
        end: ISO-8601 end datetime.
        calendar_uid: Calendar to add the event to (uses default if omitted).
        location: Optional location string.
        description: Optional description / notes.

    Returns:
        The created event as a dict.
    """
    start_dt = dateparser.parse(start)
    end_dt = dateparser.parse(end)

    calendars = api.calendar.calendars()
    if calendar_uid:
        cal = next((c for c in calendars if c.get("guid") == calendar_uid), None)
        if cal is None:
            raise ValueError(f"Calendar '{calendar_uid}' not found.")
    else:
        cal = next((c for c in calendars if c.get("isDefault")), calendars[0])

    event = api.calendar.add_event(
        title=title,
        start_date=start_dt,
        end_date=end_dt,
        location=location,
        description=description,
        guid=cal.get("guid"),
    )
    return _fmt_event(event)
