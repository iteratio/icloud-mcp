"""iCloud Reminders tools for MCP."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dateparser


def _fmt_reminder(reminder: Any) -> dict:
    """Normalise a pyicloud reminder to a plain dict."""
    fields = reminder if isinstance(reminder, dict) else {}
    return {
        "uid": fields.get("guid", ""),
        "title": fields.get("title", "(no title)"),
        "description": fields.get("description", ""),
        "completed": fields.get("completed", False),
        "due": str(fields.get("dueDate", "")),
        "priority": fields.get("priority", 0),
        "list": fields.get("pGuid", ""),
    }


def list_lists(api: Any) -> list[dict]:
    """Return all reminder lists."""
    lists = api.reminders.lists
    return [
        {
            "uid": lst.get("guid", ""),
            "title": lst.get("title", ""),
        }
        for lst in lists
    ]


def list_reminders(
    api: Any,
    list_uid: str | None = None,
    include_completed: bool = False,
) -> list[dict]:
    """
    Return reminders, optionally filtered by list and completion status.

    Args:
        api: Authenticated PyiCloudService instance.
        list_uid: Restrict to a specific reminder list UID.
        include_completed: Include completed reminders (default: False).
    """
    all_reminders: list[dict] = []

    for lst_title, reminders in api.reminders.lists.items():
        for r in reminders:
            all_reminders.append(_fmt_reminder(r))

    if list_uid:
        all_reminders = [r for r in all_reminders if r["list"] == list_uid]

    if not include_completed:
        all_reminders = [r for r in all_reminders if not r["completed"]]

    return all_reminders


def create_reminder(
    api: Any,
    title: str,
    list_uid: str | None = None,
    due: str | None = None,
    description: str = "",
    priority: int = 0,
) -> dict:
    """
    Create a new reminder.

    Args:
        api: Authenticated PyiCloudService instance.
        title: Reminder title.
        list_uid: Reminder list UID (uses default list if omitted).
        due: Optional ISO-8601 due date/time.
        description: Optional notes.
        priority: 0 = none, 1 = high, 5 = medium, 9 = low.

    Returns:
        The created reminder as a dict.
    """
    due_dt: datetime | None = None
    if due:
        due_dt = dateparser.parse(due)

    result = api.reminders.post(
        title=title,
        description=description,
        due_date=due_dt,
        priority=priority,
        collection=list_uid,
    )
    return _fmt_reminder(result)


def complete_reminder(api: Any, uid: str) -> bool:
    """
    Mark a reminder as completed.

    Args:
        api: Authenticated PyiCloudService instance.
        uid: The reminder UID.

    Returns:
        True if found and marked complete, False if not found.
    """
    for lst_title, reminders in api.reminders.lists.items():
        for r in reminders:
            if r.get("guid") == uid:
                r["completed"] = True
                r["completionDate"] = datetime.now(tz=timezone.utc).isoformat()
                api.reminders.post(collection=r.get("pGuid"), **r)
                return True
    return False
