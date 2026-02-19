"""iCloud Calendar tools — CalDAV implementation.

Uses Apple's official CalDAV endpoint with Basic Auth (app-specific password).
No pyicloud dependency.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import caldav
from dateutil import parser as dateparser
from icalendar import Calendar as iCalendar
from icalendar import Event as iCalEvent

ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"


def _client(apple_id: str, app_password: str) -> caldav.DAVClient:
    """Return an authenticated CalDAV client."""
    return caldav.DAVClient(
        url=ICLOUD_CALDAV_URL,
        username=apple_id,
        password=app_password,
    )


def _fmt_calendar(cal: caldav.Calendar) -> dict:
    return {
        "uid": str(cal.id),
        "title": cal.name or "(unnamed)",
        "url": str(cal.url),
    }


def _fmt_event(vevent: Any) -> dict:
    """Extract a plain dict from a vobject/icalendar VEVENT component."""
    def _str(val: Any) -> str:
        if val is None:
            return ""
        if hasattr(val, "dt"):
            return val.dt.isoformat() if val.dt else ""
        return str(val)

    return {
        "uid": _str(vevent.get("uid")),
        "title": _str(vevent.get("summary")),
        "start": _str(vevent.get("dtstart")),
        "end": _str(vevent.get("dtend")),
        "location": _str(vevent.get("location")),
        "description": _str(vevent.get("description")),
    }


def list_calendars(apple_id: str, app_password: str) -> list[dict]:
    """Return all calendars for the account."""
    client = _client(apple_id, app_password)
    principal = client.principal()
    return [_fmt_calendar(c) for c in principal.calendars()]


def list_events(
    apple_id: str,
    app_password: str,
    from_date: str | None = None,
    to_date: str | None = None,
    calendar_uid: str | None = None,
) -> list[dict]:
    """
    Return events in the given date range.

    Args:
        apple_id: iCloud Apple ID.
        app_password: App-specific password.
        from_date: ISO-8601 start date (default: today).
        to_date: ISO-8601 end date (default: 7 days from today).
        calendar_uid: Restrict to a specific calendar by UID.
    """
    now = datetime.now(tz=timezone.utc)
    start = dateparser.parse(from_date) if from_date else now
    end = dateparser.parse(to_date) if to_date else now + timedelta(days=7)

    client = _client(apple_id, app_password)
    principal = client.principal()
    calendars = principal.calendars()

    if calendar_uid:
        calendars = [c for c in calendars if str(c.id) == calendar_uid]

    results: list[dict] = []
    for cal in calendars:
        try:
            events = cal.search(start=start, end=end, event=True, expand=True)
            for ev in events:
                cal_data = iCalendar.from_ical(ev.data)
                for component in cal_data.walk():
                    if component.name == "VEVENT":
                        d = _fmt_event(component)
                        d["calendar"] = cal.name or ""
                        results.append(d)
        except Exception:  # noqa: BLE001
            continue

    return results


def get_event(
    apple_id: str,
    app_password: str,
    event_uid: str,
) -> dict | None:
    """Return a single event by UID, or None if not found."""
    client = _client(apple_id, app_password)
    principal = client.principal()

    for cal in principal.calendars():
        try:
            events = cal.search(event=True)
            for ev in events:
                cal_data = iCalendar.from_ical(ev.data)
                for component in cal_data.walk():
                    if component.name == "VEVENT":
                        uid = str(component.get("uid", ""))
                        if uid == event_uid:
                            d = _fmt_event(component)
                            d["calendar"] = cal.name or ""
                            return d
        except Exception:  # noqa: BLE001
            continue

    return None


def create_event(
    apple_id: str,
    app_password: str,
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
        apple_id: iCloud Apple ID.
        app_password: App-specific password.
        title: Event title.
        start: ISO-8601 start datetime.
        end: ISO-8601 end datetime.
        calendar_uid: Calendar to add the event to (uses first calendar if omitted).
        location: Optional location string.
        description: Optional description / notes.

    Returns:
        The created event as a dict.
    """
    start_dt = dateparser.parse(start)
    end_dt = dateparser.parse(end)

    client = _client(apple_id, app_password)
    principal = client.principal()
    calendars = principal.calendars()

    if calendar_uid:
        cal = next((c for c in calendars if str(c.id) == calendar_uid), None)
        if cal is None:
            raise ValueError(f"Calendar '{calendar_uid}' not found.")
    else:
        cal = calendars[0]

    # Build iCal payload
    event_uid = str(uuid.uuid4())
    ical = iCalendar()
    ical.add("prodid", "-//icloud-mcp//EN")
    ical.add("version", "2.0")

    ev = iCalEvent()
    ev.add("uid", event_uid)
    ev.add("summary", title)
    ev.add("dtstart", start_dt)
    ev.add("dtend", end_dt)
    ev.add("dtstamp", datetime.now(tz=timezone.utc))
    if location:
        ev.add("location", location)
    if description:
        ev.add("description", description)

    ical.add_component(ev)
    cal.add_event(ical.to_ical().decode())

    return {
        "uid": event_uid,
        "title": title,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "location": location,
        "description": description,
        "calendar": cal.name or "",
    }
